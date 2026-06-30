"""
Engine-level question-mode API tests.

Covers the engine surface for QuestionRequest lifecycle and the
Pydantic-validated REST endpoint shapes. The architectural model is
the agent-interrupt pattern: tool returns immediately, engine pauses,
external reply resumes the loop.
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from harness.engine.engine import AgentEngine, EngineConfig, PendingQuestion
from harness.engine.state_machine import EngineState
from harness.storage.backends.memory import MemorySessionStore
from harness.types.questions import (
    QuestionOption, QuestionPrompt, QuestionRequest,
)
from api.rest import app


# ── helpers ────────────────────────────────────────────────────────────────

def _make_engine(question_mode: str = "noquestion") -> AgentEngine:
    cfg = EngineConfig(session_id=f"s-{question_mode}", question_mode=question_mode)
    return AgentEngine(
        config=cfg, loop=MagicMock(), session_store=MemorySessionStore(),
        emitter=MagicMock(), tool_registry=MagicMock(),
    )


# ── question mode flag ────────────────────────────────────────────────────

def test_question_mode_default_is_noquestion():
    e = _make_engine()
    assert e.get_question_mode() == "noquestion"


def test_set_question_mode_updates_value():
    import asyncio
    e = _make_engine()
    asyncio.run(e.set_question_mode("question"))
    assert e.get_question_mode() == "question"


def test_set_question_mode_normalizes_invalid():
    import asyncio
    e = _make_engine()
    asyncio.run(e.set_question_mode("garbage"))
    assert e.get_question_mode() == "noquestion"


# ── canonical name: PendingQuestion is QuestionRequest ────────────────────

def test_pending_question_canonical_alias():
    """The legacy name must be the same class as QuestionRequest."""
    from harness.types.questions import QuestionRequest as QR
    assert PendingQuestion is QR


# ── REST endpoints are registered ─────────────────────────────────────────

def test_mode_endpoint_registered():
    paths = {(r.path, tuple(r.methods)) for r in app.routes if hasattr(r, "methods")}
    assert any(p == "/sessions/{session_id}/mode" and "PATCH" in m for p, m in paths)
    assert any(p == "/sessions/{session_id}/questions/{request_id}/reply" and "POST" in m
               for p, m in paths)
    assert any(p == "/sessions/{session_id}/questions/{request_id}/reject" and "POST" in m
               for p, m in paths)


# ── engine registration / rejection / reply semantics ─────────────────────

@pytest.mark.asyncio
async def test_register_and_reply_round_trip():
    e = _make_engine("question")
    prompts = [
        QuestionPrompt(
            question="Q?",
            options=[QuestionOption(label="A"), QuestionOption(label="B")],
        )
    ]
    await e.register_question_request(
        request_id="rt-1", tool_call_id="tc-1", questions=prompts,
    )
    snap = await e.get_snapshot()
    assert len(snap["pending_question_requests"]) == 1
    assert snap["pending_question_requests"][0]["status"] == "pending"

    r = await e.submit_question_reply("rt-1", [["A"]])
    assert r["ok"] is True
    assert r["status"] == "answered"

    snap2 = await e.get_snapshot()
    assert snap2["pending_question_requests"] == []


@pytest.mark.asyncio
async def test_register_and_reject_round_trip():
    e = _make_engine("question")
    prompts = [
        QuestionPrompt(
            question="Q?",
            options=[QuestionOption(label="A"), QuestionOption(label="B")],
        )
    ]
    await e.register_question_request(
        request_id="rt-2", tool_call_id="tc-2", questions=prompts,
    )
    r = await e.reject_question("rt-2")
    assert r["ok"] is True
    assert r["status"] == "rejected"
    snap = await e.get_snapshot()
    assert snap["pending_question_requests"] == []


@pytest.mark.asyncio
async def test_unknown_request_returns_error():
    e = _make_engine("question")
    r = await e.submit_question_reply("nope", [["A"]])
    assert r["ok"] is False
    assert "not found" in r["detail"]


# ── single / multi-select on the engine side ─────────────────────────────

@pytest.mark.asyncio
async def test_multi_select_answers_accepted():
    e = _make_engine("question")
    prompts = [
        QuestionPrompt(
            question="Which features?",
            options=[
                QuestionOption(label="A"),
                QuestionOption(label="B"),
                QuestionOption(label="C"),
            ],
            multiple=True, custom=True,
        )
    ]
    await e.register_question_request(
        request_id="ms-1", tool_call_id="tc-ms", questions=prompts,
    )
    r = await e.submit_question_reply("ms-1", [["A", "B", "free text"]])
    assert r["ok"], r
    assert r["status"] == "answered"


# ── cancellation emits question.resolved with status=expired ─────────────

@pytest.mark.asyncio
async def test_cancel_expires_pending_requests():
    e = _make_engine("question")
    received: list[dict] = []
    async def listener(event):
        received.append(event)
    e.add_event_listener(listener)

    prompts = [QuestionPrompt(
        question="Q?",
        options=[QuestionOption(label="A"), QuestionOption(label="B")],
    )]
    await e.register_question_request(
        request_id="cx-1", tool_call_id="tcx-1", questions=prompts,
    )
    await e.cancel()
    snap = await e.get_snapshot()
    assert snap["pending_question_requests"] == []
    assert any(
        e["type"] == "question.resolved" and e["data"]["status"] == "expired"
        for e in received
    ), received
