"""
REST API for the agent harness.

Backend is the single source of truth.
Frontends MUST pull state from GET /sessions/{id}/state — never cache locally.
Switching sessions: call /state to get last_messages + is_running.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
load_dotenv(override=False)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from harness.config import HarnessConfig
from harness.engine.engine import AgentEngine
from harness.factory import build_engine
from harness.skills import (
    load_persona,
    list_skills, list_personas,
    read_file_safe, write_file_safe,
    SKILLS_DIR, PERSONAS_DIR,
)
from harness.storage.backends.memory import MemorySessionStore
from harness.storage.backends.sqlite import SQLiteSessionStore

app = FastAPI(title="MyHarnessPy", version="0.1.0")

# Active engines: session_id -> AgentEngine
_engines: dict[str, AgentEngine] = {}
_engine_meta: dict[str, dict[str, Any]] = {}   # session_id -> {persona, provider}

# Shared config — loaded once at startup
_config: HarnessConfig | None = None
_session_store = MemorySessionStore()


# ── Startup ────────────────────────────────────────────────────────────

@app.on_event("startup")
async def _startup() -> None:
    global _config, _session_store
    try:
        _config = HarnessConfig.from_yaml("config.yaml")
    except FileNotFoundError:
        _config = HarnessConfig.from_env()

    if _config.storage.backend == "sqlite":
        _session_store = SQLiteSessionStore(_config.storage.path)


# ── Static files ───────────────────────────────────────────────────────

STATIC_DIR = Path("static")

@app.get("/", include_in_schema=False)
async def serve_index() -> FileResponse:
    index = STATIC_DIR / "index.html"
    if not index.exists():
        raise HTTPException(status_code=404, detail="Frontend not found. Run setup first.")
    return FileResponse(str(index))

@app.on_event("startup")
async def _mount_static() -> None:
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ── Request / response models ──────────────────────────────────────────

class CreateSessionRequest(BaseModel):
    session_id: str = ""       # optional; pass to restore after server reload
    provider: str = ""
    persona: str = ""           # load from personas/{name}.md (preferred)
    system_prompt: str = ""     # fallback if no persona
    allowed_tools: list[str] | None = None


class SendMessageRequest(BaseModel):
    text: str


class RewriteMessageRequest(BaseModel):
    text: str


class SetModeRequest(BaseModel):
    question_mode: str   # "question" | "noquestion"


class ClarificationAnswerRequest(BaseModel):
    """Legacy single-question reply shape."""
    request_id: str
    answer: str | list[str]   # str for single, list for multi_select


class QuestionReplyRequest(BaseModel):
    """
    New OpenCode-style structured reply.

    `answers` is a list whose length must equal the number of questions in the
    pending request. Each inner list contains the selected option labels for
    that question (and at most one custom text entry when custom=true).
    """
    answers: list[list[str]]


class ConfigWriteRequest(BaseModel):
    content: str


class CreateFileRequest(BaseModel):
    name: str
    content: str


# ── Session routes ─────────────────────────────────────────────────────

@app.post("/sessions", status_code=201)
async def create_session(req: CreateSessionRequest) -> dict[str, Any]:
    cfg = _require_config()

    provider_name, system_prompt, allowed_tools = _resolve_session_config(req, cfg)

    if provider_name not in cfg.providers:
        raise HTTPException(
            status_code=400,
            detail=f"Provider '{provider_name}' not found in config. "
                   f"Available: {list(cfg.providers.keys())}",
        )

    session_id = req.session_id or str(uuid.uuid4())
    # If restoring an existing session, load its previous question_mode
    question_mode = "noquestion"
    try:
        rec = await _session_store.load(session_id)
        if rec and isinstance(rec.metadata, dict):
            question_mode = rec.metadata.get("question_mode", "noquestion") or "noquestion"
    except Exception:
        pass
    engine = build_engine(
        session_id=session_id,
        provider_cfg=cfg.providers[provider_name],
        harness_cfg=cfg,
        session_store=_session_store,
        system_prompt=system_prompt,
        allowed_tools=allowed_tools,
        engine_registry=_engines,
        provider_name=provider_name,
        question_mode=question_mode,
    )
    await engine.restore_from_store()
    _engines[session_id] = engine
    _engine_meta[session_id] = {
        "provider": provider_name,
        "persona":  req.persona,
        "question_mode": question_mode,
    }
    return {
        "session_id": session_id,
        "provider":   provider_name,
        "persona":    req.persona,
    }


@app.post("/sessions/{session_id}/messages")
async def send_message(session_id: str, req: SendMessageRequest) -> dict[str, Any]:
    engine = _get_engine(session_id)
    await engine.send_message(req.text)
    return {"status": "accepted"}


@app.patch("/sessions/{session_id}/messages/{message_id}")
async def rewrite_message(
    session_id: str, message_id: str,
    re_run: bool = False,
    req: RewriteMessageRequest | None = None,
) -> dict[str, Any]:
    """
    Rewrite a user message by message_id and roll back all subsequent messages.
    Body: { "text": "new message content" }
    Query param re_run=true: immediately re-execute from the rewritten message.
    Returns {found, rollback_count, session_version}.
    """
    engine = _get_engine(session_id)
    if req is None:
        raise HTTPException(status_code=400, detail="Request body required")
    result = await engine.rewrite_message(message_id, req.text)
    if not result["found"]:
        raise HTTPException(status_code=404, detail=f"Message {message_id!r} not found")
    if re_run:
        # Find the rewritten message to get its message_id for re_run_from
        result["re_run_triggered"] = True
        # re_run_from needs the message_id — it's the same one we just rewrote
        asyncio.create_task(engine.re_run_from(message_id))
    return result


@app.get("/sessions/{session_id}/state")
async def get_state(session_id: str) -> dict[str, Any]:
    engine = _get_engine(session_id)
    snapshot = await engine.get_snapshot()
    meta = dict(_engine_meta.get(session_id, {}))
    try:
        rec = await _session_store.load(session_id)
        if rec and isinstance(rec.metadata, dict):
            store_meta = rec.metadata
            if not meta.get("title"):
                meta["title"] = store_meta.get("title", "")
            if not meta.get("display_name"):
                meta["display_name"] = store_meta.get("display_name", "")
    except Exception:
        pass
    snapshot["meta"] = meta
    return snapshot


@app.post("/sessions/{session_id}/cancel")
async def cancel_session(session_id: str) -> dict[str, Any]:
    engine = _get_engine(session_id)
    await engine.cancel()
    return {"status": "cancel_requested"}


@app.post("/sessions/{session_id}/confirm")
async def confirm_action(session_id: str) -> dict[str, Any]:
    engine = _get_engine(session_id)
    await engine.confirm()
    return {"status": "confirmed"}


@app.post("/sessions/{session_id}/deny")
async def deny_action(session_id: str) -> dict[str, Any]:
    engine = _get_engine(session_id)
    await engine.deny()
    return {"status": "denied"}


@app.delete("/sessions/{session_id}/pending/{index}")
async def cancel_pending_command(session_id: str, index: int) -> dict[str, Any]:
    """
    Cancel a queued command (pending_commands index) or pending sub-agent spawn.
    Returns {"cancelled": true} if found, 404 otherwise.
    """
    engine = _get_engine(session_id)

    # Try pending commands first
    if await engine.cancel_pending_command(index):
        return {"cancelled": True, "type": "command", "index": index}

    # Try pending spawns
    if await engine.cancel_pending_spawn(index):
        return {"cancelled": True, "type": "spawn", "index": index}

    raise HTTPException(status_code=404, detail=f"Pending item {index} not found")


@app.patch("/sessions/{session_id}/mode")
async def set_session_mode(session_id: str, req: SetModeRequest) -> dict[str, Any]:
    """
    Update a session's question mode ("question" or "noquestion").
    Toggling on at runtime registers the ask_user tool on the existing engine.
    Toggling off unregisters it (the LLM will no longer see it in its tool list).
    """
    engine = _get_engine(session_id)
    new_mode = await engine.set_question_mode(req.question_mode)
    if _engine_meta.get(session_id) is not None:
        _engine_meta[session_id]["question_mode"] = new_mode

    # Update tool registry: register or unregister ask_user
    try:
        from harness.tools.builtin.ask_user import (
            ASK_USER_SCHEMA, make_ask_user_tool,
        )
        reg = engine._tool_registry
        existing = {t.schema.name for t in reg.discover()} if reg else set()
        if new_mode == "question" and "ask_user" not in existing:
            reg.register(ASK_USER_SCHEMA, make_ask_user_tool(engine))
        elif new_mode == "noquestion" and "ask_user" in existing:
            reg.unregister("ask_user")
    except Exception as e:
        # Tool registry update is best-effort
        pass

    # Push state so frontend sees the change
    await engine._notify_state_listeners()
    return {"session_id": session_id, "question_mode": new_mode}


@app.post("/sessions/{session_id}/clarifications")
async def submit_clarification(
    session_id: str, req: ClarificationAnswerRequest
) -> dict[str, Any]:
    """
    Submit the user's answer to a pending clarification question.
    Unblocks the running ask_user tool and lets the loop continue.
    """
    engine = _get_engine(session_id)
    result = await engine.submit_clarification_answer(req.request_id, req.answer)
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail=result.get("detail", "not found"))
    return result


# ── New OpenCode-style question endpoints ──────────────────────────────────
#
# These coexist with the legacy /clarifications endpoints. Frontends that
# already speak the old shape keep working; new clients should prefer these.

@app.post("/sessions/{session_id}/questions/{request_id}/reply")
async def reply_to_question(
    session_id: str, request_id: str, req: QuestionReplyRequest
) -> dict[str, Any]:
    """
    Submit answers for a pending question request.

    Body: { "answers": [["opt1", "opt2"], ["opt3"]] }
      - answers.length must equal questions.length (validated server-side)
      - per-question validation: see harness.types.questions.validate_answers_against_questions

    Returns {"ok": true, ...} or raises 404 / 400 with {"detail": ...}.
    The agent run resumes immediately on success.
    """
    engine = _get_engine(session_id)
    result = await engine.submit_question_reply(request_id, req.answers)
    if result.get("ok"):
        return result
    # Validation failures → 400; missing request → 404
    code = result.get("code")
    if code == "invalid_answers":
        raise HTTPException(status_code=400, detail=result.get("detail", "invalid"))
    raise HTTPException(status_code=404, detail=result.get("detail", "not found"))


@app.post("/sessions/{session_id}/questions/{request_id}/reject")
async def reject_question(session_id: str, request_id: str) -> dict[str, Any]:
    """
    Skip / reject a pending question. The agent run resumes with a synthetic
    "user skipped" message; the LLM is expected to proceed with defaults.
    """
    engine = _get_engine(session_id)
    result = await engine.reject_question(request_id)
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail=result.get("detail", "not found"))
    return result


@app.get("/sessions")
async def list_sessions() -> dict[str, Any]:
    sessions = []
    for sid, eng in _engines.items():
        meta = _engine_meta.get(sid, {})
        # Also read store metadata for title/display_name generated asynchronously
        store_title = ""
        store_display_name = ""
        store_meta: dict = {}
        try:
            rec = await _session_store.load(sid)
            if rec and isinstance(rec.metadata, dict):
                store_meta = rec.metadata
                store_title = store_meta.get("title", "")
                store_display_name = store_meta.get("display_name", "")
        except Exception:
            pass

        sessions.append({
            "session_id":    sid,
            "state":         eng._sm.state.name,
            "persona":       meta.get("persona", store_meta.get("persona", "")),
            "provider":      meta.get("provider", store_meta.get("provider", "")),
            "title":         meta.get("title", "") or store_title,
            "display_name":  meta.get("display_name", "") or store_display_name,
            "spawn_depth":   meta.get("spawn_depth", store_meta.get("spawn_depth", 0)),
            "question_mode": eng.get_question_mode(),
        })
    return {"sessions": sessions}


@app.delete("/sessions/{session_id}", status_code=204)
async def delete_session(session_id: str):
    if session_id not in _engines:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    engine = _engines.pop(session_id)
    _engine_meta.pop(session_id, None)
    await engine.cancel()
    await _session_store.delete(session_id)


# ── Config overview ────────────────────────────────────────────────────

@app.get("/config/overview")
async def config_overview() -> dict[str, Any]:
    """All config data needed to render the frontend sidebar."""
    cfg = _require_config()
    return {
        "skills":           list_skills(),
        "personas":         list_personas(),      # [{name, description}]
        "providers":        list(cfg.providers.keys()),
        "default_provider": cfg.default_provider,
        "tools_enabled":    cfg.tools.enabled,
    }


# ── Skills CRUD (folder-based) ─────────────────────────────────────────

@app.get("/config/skills")
async def api_list_skills() -> dict[str, Any]:
    return {"skills": list_skills()}


@app.get("/config/skills/{name}")
async def api_get_skill(name: str) -> dict[str, Any]:
    folder_md = SKILLS_DIR / name / "SKILL.md"
    if folder_md.exists():
        return {"name": name, "content": folder_md.read_text(encoding="utf-8"), "format": "folder"}
    legacy_md = SKILLS_DIR / f"{name}.md"
    if legacy_md.exists():
        return {"name": name, "content": legacy_md.read_text(encoding="utf-8"), "format": "md"}
    raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")


@app.put("/config/skills/{name}")
async def api_save_skill(name: str, req: ConfigWriteRequest) -> dict[str, Any]:
    _check_safe_name(name)
    write_file_safe(SKILLS_DIR / name / "SKILL.md", req.content)
    return {"status": "saved", "name": name}


@app.post("/config/skills")
async def api_create_skill(req: CreateFileRequest) -> dict[str, Any]:
    _check_safe_name(req.name)
    path = SKILLS_DIR / req.name / "SKILL.md"
    if path.exists():
        raise HTTPException(status_code=409, detail=f"Skill '{req.name}' already exists")
    write_file_safe(path, req.content)
    return {"status": "created", "name": req.name}


@app.delete("/config/skills/{name}", status_code=204)
async def api_delete_skill(name: str):
    import shutil
    folder = SKILLS_DIR / name
    if folder.is_dir():
        shutil.rmtree(folder)
        return
    legacy = SKILLS_DIR / f"{name}.md"
    if legacy.exists():
        legacy.unlink()
        return
    raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")


# ── Personas CRUD ──────────────────────────────────────────────────────

@app.get("/config/personas")
async def api_list_personas() -> dict[str, Any]:
    return {"personas": list_personas()}


@app.get("/config/personas/{name}")
async def api_get_persona(name: str) -> dict[str, Any]:
    path = PERSONAS_DIR / f"{name}.md"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Persona '{name}' not found")
    return {"name": name, "content": path.read_text(encoding="utf-8")}


@app.put("/config/personas/{name}")
async def api_save_persona(name: str, req: ConfigWriteRequest) -> dict[str, Any]:
    _check_safe_name(name)
    write_file_safe(PERSONAS_DIR / f"{name}.md", req.content)
    return {"status": "saved", "name": name}


@app.post("/config/personas")
async def api_create_persona(req: CreateFileRequest) -> dict[str, Any]:
    _check_safe_name(req.name)
    path = PERSONAS_DIR / f"{req.name}.md"
    if path.exists():
        raise HTTPException(status_code=409, detail=f"Persona '{req.name}' already exists")
    write_file_safe(path, req.content)
    return {"status": "created", "name": req.name}


@app.delete("/config/personas/{name}", status_code=204)
async def api_delete_persona(name: str):
    path = PERSONAS_DIR / f"{name}.md"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Persona '{name}' not found")
    path.unlink()


# ── config.yaml CRUD ───────────────────────────────────────────────────

@app.get("/config/yaml")
async def api_get_yaml() -> dict[str, Any]:
    path = Path("config.yaml")
    if not path.exists():
        raise HTTPException(status_code=404, detail="config.yaml not found")
    return {"content": path.read_text(encoding="utf-8")}


@app.put("/config/yaml")
async def api_save_yaml(req: ConfigWriteRequest) -> dict[str, Any]:
    import yaml
    try:
        yaml.safe_load(req.content)   # validate before writing
    except yaml.YAMLError as e:
        raise HTTPException(status_code=400, detail=f"Invalid YAML: {e}")
    Path("config.yaml").write_text(req.content, encoding="utf-8")
    return {"status": "saved"}


# ── Helpers ────────────────────────────────────────────────────────────

def _check_safe_name(name: str) -> None:
    """Prevent path traversal in file names."""
    if not name or "/" in name or "\\" in name or ".." in name:
        raise HTTPException(status_code=400, detail=f"Invalid name: '{name}'")


def _require_config() -> HarnessConfig:
    if _config is None:
        raise HTTPException(status_code=503, detail="Config not loaded yet")
    return _config


def _get_engine(session_id: str) -> AgentEngine:
    if session_id not in _engines:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return _engines[session_id]


def _resolve_session_config(
    req: CreateSessionRequest, cfg: HarnessConfig
) -> tuple[str, str, list[str] | None]:
    """Returns (provider, system_prompt, allowed_tools)."""
    provider      = req.provider or cfg.default_provider
    system_prompt = req.system_prompt
    allowed_tools = req.allowed_tools

    if req.persona:
        try:
            persona = load_persona(req.persona)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        system_prompt = persona.get("system_prompt", system_prompt)
        allowed_tools = persona.get("allowed_tools") or allowed_tools
        if persona.get("provider"):
            provider = persona["provider"]

    return provider, system_prompt, allowed_tools


# ── WebSocket router ────────────────────────────────────────────────────
# Imported at the bottom to avoid circular import:
#   ws.py  imports  _engines / _get_engine  from here (defined above ✓)
#   rest.py imports router from ws.py (done after everything is defined ✓)
from api.ws import router as _ws_router  # noqa: E402
app.include_router(_ws_router)
