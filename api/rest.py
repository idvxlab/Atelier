"""
REST API for the agent harness.

Backend is the single source of truth.
Frontends MUST pull state from GET /sessions/{id}/state — never cache locally.
Switching sessions: call /state to get last_messages + is_running.
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
load_dotenv(override=False)

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from harness.config import HarnessConfig, ProviderConfig
from harness.engine.compression import CompressionConfig, ContextCompressor
from harness.engine.engine import AgentEngine, EngineConfig
from harness.engine.loop import ReactLoop
from harness.llm.registry import build_provider
from harness.observability.events import EventEmitter
from harness.skills import (
    load_persona,
    list_skills, list_personas,
    read_file_safe, write_file_safe,
    build_skill_system_addendum,
    SKILLS_DIR, PERSONAS_DIR,
)
from harness.storage.backends.memory import MemorySessionStore
from harness.storage.backends.sqlite import SQLiteSessionStore
from harness.tools.builtin import (
    READ_FILE_SCHEMA, read_file_tool,
    SEARCH_SCHEMA, search_tool,
    SHELL_SCHEMA, shell_tool,
    USE_SKILL_SCHEMA, use_skill_tool,
)
from harness.tools.executor import ToolExecutor
from harness.tools.overflow import OverflowStore
from harness.tools.registry import ToolRegistry

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
    provider: str = ""
    persona: str = ""           # load from personas/{name}.md (preferred)
    system_prompt: str = ""     # fallback if no persona
    allowed_tools: list[str] | None = None


class SendMessageRequest(BaseModel):
    text: str


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

    session_id = str(uuid.uuid4())
    engine = _build_engine(
        session_id=session_id,
        provider_cfg=cfg.providers[provider_name],
        harness_cfg=cfg,
        system_prompt=system_prompt,
        allowed_tools=allowed_tools,
    )
    _engines[session_id] = engine
    _engine_meta[session_id] = {
        "provider": provider_name,
        "persona":  req.persona,
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


@app.get("/sessions/{session_id}/state")
async def get_state(session_id: str) -> dict[str, Any]:
    engine = _get_engine(session_id)
    snapshot = await engine.get_snapshot()
    snapshot["meta"] = _engine_meta.get(session_id, {})
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


@app.get("/sessions")
async def list_sessions() -> dict[str, Any]:
    sessions = []
    for sid, eng in _engines.items():
        meta = _engine_meta.get(sid, {})
        sessions.append({
            "session_id": sid,
            "state":      eng._sm.state.name,
            "persona":    meta.get("persona", ""),
            "provider":   meta.get("provider", ""),
        })
    return {"sessions": sessions}


@app.delete("/sessions/{session_id}", status_code=204)
async def delete_session(session_id: str) -> None:
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
async def api_delete_skill(name: str) -> None:
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
async def api_delete_persona(name: str) -> None:
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


def _build_engine(
    session_id: str,
    provider_cfg: ProviderConfig,
    harness_cfg: HarnessConfig,
    system_prompt: str = "",
    allowed_tools: list[str] | None = None,
) -> AgentEngine:
    emitter = EventEmitter(session_id)
    llm = build_provider(provider_cfg)

    comp = harness_cfg.compression
    summarizer = (
        build_provider(harness_cfg.providers[comp.summary_provider])
        if comp.summary_provider and comp.summary_provider in harness_cfg.providers
        else llm
    )

    # Append skill descriptions so agent knows which skills are available
    skills = list_skills()
    full_system = system_prompt + build_skill_system_addendum(skills)

    compressor = ContextCompressor(
        summarizer=summarizer,
        config=CompressionConfig(
            token_window=comp.token_window,
            auto_trigger_ratio=comp.auto_trigger_ratio,
            micro_keep_recent=comp.micro_keep_recent,
            system_identity=full_system,
        ),
    )

    ALL_TOOLS = {
        "read_file": (READ_FILE_SCHEMA, read_file_tool),
        "search":    (SEARCH_SCHEMA,    search_tool),
        "shell":     (SHELL_SCHEMA,     shell_tool),
    }

    global_enabled = harness_cfg.tools.enabled
    if allowed_tools is not None:
        tools_to_load = [t for t in allowed_tools if global_enabled is None or t in global_enabled]
    else:
        tools_to_load = global_enabled if global_enabled is not None else list(ALL_TOOLS.keys())

    registry = ToolRegistry()
    for name in tools_to_load:
        if name in ALL_TOOLS:
            schema, handler = ALL_TOOLS[name]
            registry.register(schema, handler)

    # use_skill is always registered if skills exist
    if skills:
        registry.register(USE_SKILL_SCHEMA, use_skill_tool)

    overflow = OverflowStore()
    executor = ToolExecutor(
        registry=registry,
        overflow=overflow,
        emitter=emitter,
        limits=harness_cfg.tools.limits,
    )

    loop = ReactLoop(
        llm=llm,
        tool_registry=registry,
        tool_executor=executor,
        compressor=compressor,
        emitter=emitter,
        max_rounds=harness_cfg.engine.max_rounds,
    )

    return AgentEngine(
        config=EngineConfig(
            session_id=session_id,
            system_prompt=full_system,
        ),
        loop=loop,
        session_store=_session_store,
        emitter=emitter,
    )
