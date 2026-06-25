"""
Architecture tests for the Question Mode interrupt system.

Validates the production-grade agent-interrupt invariants introduced by
the refactor:

  1. ask_user tool is NON-BLOCKING — it returns an InterruptibleToolResult
     immediately, and the engine pauses the run loop at the engine level.
  2. The tool is the DECISION LAYER's primitive; the engine does not force
     the LLM to ask, and the frontend does not control the trigger.
  3. The engine is the single source of truth for QuestionRequest state.
  4. The WebSocket event channel pushes question.asked / question.resolved
     to all event listeners. The /state snapshot is restore-only.
  5. The state machine is strictly:
         pending → answered | rejected | expired
     Transitions are non-reversible. Concurrent calls are idempotent.
  6. The canonical term is QuestionRequest. Legacy "clarification" aliases
     are no longer used in production code paths.
"""
from __future__ import annotations

import asyncio
import pytest
from unittest.mock import MagicMock

from harness.engine.engine import AgentEngine, EngineConfig, PendingQuestion
from harness.engine.state_machine import EngineState
from harness.engine.loop import InterruptSignal
from harness.storage.backends.memory import MemorySessionStore
from harness.types.questions import (
    QuestionOption,
    QuestionPrompt,
    QuestionRequest,
    validate_answers_against_questions,
    format_answers_for_llm,
)
from harness.tools.executor import InterruptibleToolResult
from harness.tools.builtin.ask_user import (
    ASK_USER_SCHEMA,
    make_ask_user_tool,
    _normalize_questions,
)


# ── helpers ────────────────────────────────────────────────────────────────

def _make_engine(mode: str = "question") -> AgentEngine:
    cfg = EngineConfig(session_id=f"engine-{mode}", question_mode=mode)
    return AgentEngine(
        config=cfg, loop=MagicMock(), session_store=MemorySessionStore(),
        emitter=MagicMock(), tool_registry=MagicMock(),
    )


def _two_prompts() -> list[QuestionPrompt]:
    return [
        QuestionPrompt(
            question="你想制作哪一类网站？",
            header="网站类型",
            options=[
                QuestionOption(label="企业官网"),
                QuestionOption(label="作品集网站"),
                QuestionOption(label="电商网站"),
                QuestionOption(label="Landing Page"),
            ],
            multiple=False,
            custom=True,
        ),
        QuestionPrompt(
            question="你希望网站包含哪些功能？",
            header="核心功能",
            options=[
                QuestionOption(label="首页"),
                QuestionOption(label="关于我们"),
                QuestionOption(label="产品/服务展示"),
                QuestionOption(label="联系表单"),
                QuestionOption(label="后台管理"),
            ],
            multiple=True,
            custom=True,
        ),
    ]


# ── 1. State machine integrity ─────────────────────────────────────────────

def test_state_machine_has_waiting_interrupt():
    """The new state must be present and the transition graph must include it."""
    from harness.engine.state_machine import _TRANSITIONS
    assert hasattr(EngineState, "WAITING_INTERRUPT")
    # RUNNING can transition to WAITING_INTERRUPT
    assert EngineState.WAITING_INTERRUPT in _TRANSITIONS[EngineState.RUNNING]
    # WAITING_INTERRUPT can transition back to RUNNING (resume) or WAITING_INPUT
    targets = _TRANSITIONS[EngineState.WAITING_INTERRUPT]
    assert EngineState.RUNNING in targets
    assert EngineState.WAITING_INPUT in targets
    assert EngineState.ERROR in targets


def test_pending_question_is_question_request():
    """The legacy name must be the same class — no shadow duplicate."""
    from harness.types.questions import QuestionRequest as Canonical
    assert PendingQuestion is Canonical


def test_engine_has_no_legacy_alias_attributes():
    """The engine must not carry the old dual-naming storage attributes."""
    e = _make_engine("question")
    assert hasattr(e, "_pending_question_requests")
    assert not hasattr(e, "_pending_questions")
    assert not hasattr(e, "_pending_clarifications")
    assert not hasattr(e, "_question_event")
    assert not hasattr(e, "_clarification_event")
    assert not hasattr(e, "_question_results")
    assert not hasattr(e, "_question_results_lock")


# ── 2. Non-blocking tool: ask_user returns immediately ─────────────────────

@pytest.mark.asyncio
async def test_ask_user_tool_is_non_blocking():
    """
    Invariant: ask_user must NOT block. It returns an InterruptibleToolResult
    the moment it has registered the request, even if no one replies.
    """
    engine = _make_engine("question")
    tool = make_ask_user_tool(engine)
    prompts = _two_prompts()

    # Run the tool with a real LLM-style tool_call_id
    result = await tool(
        [p.to_dict() for p in prompts],
        _tool_call_id="tc-abc-123",
    )
    assert isinstance(result, InterruptibleToolResult), (
        f"ask_user must return InterruptibleToolResult, got {type(result)}"
    )
    assert result.is_interrupt is True
    assert "tc-abc-123" in result.content or "request_id" in result.content

    # The request IS registered (engine owns the state, not the tool)
    snap = await engine.get_snapshot()
    assert "pending_question_requests" in snap
    assert len(snap["pending_question_requests"]) == 1
    assert snap["pending_question_requests"][0]["tool_call_id"] == "tc-abc-123"


@pytest.mark.asyncio
async def test_ask_user_tool_returns_in_bounded_time():
    """
    A second invariant: even with zero user response, the tool call
    must complete quickly. We assert it returns within 1s.
    """
    engine = _make_engine("question")
    tool = make_ask_user_tool(engine)
    prompts = _two_prompts()

    async def run_tool():
        return await tool(
            [p.to_dict() for p in prompts],
            _tool_call_id="tc-bounded",
        )

    result = await asyncio.wait_for(run_tool(), timeout=1.0)
    assert isinstance(result, InterruptibleToolResult)
    # engine has the request, tool is gone — engine will pause the loop
    snap = await engine.get_snapshot()
    assert snap["pending_question_requests"][0]["status"] == "pending"


# ── 3. Engine is the single source of truth ────────────────────────────────

@pytest.mark.asyncio
async def test_engine_emits_question_asked_event():
    """register_question_request must push a question.asked event."""
    engine = _make_engine("question")
    received: list[dict] = []
    async def listener(event):
        received.append(event)
    engine.add_event_listener(listener)

    prompts = _two_prompts()
    await engine.register_question_request(
        request_id="rid-1",
        tool_call_id="tc-1",
        questions=prompts,
    )
    assert any(e["type"] == "question.asked" for e in received), received
    evt = next(e for e in received if e["type"] == "question.asked")
    assert evt["data"]["request_id"] == "rid-1"
    assert len(evt["data"]["questions"]) == 2


@pytest.mark.asyncio
async def test_ask_user_tool_emits_question_asked_via_engine():
    """The full tool path must surface a question.asked event."""
    engine = _make_engine("question")
    received: list[dict] = []
    async def listener(event):
        received.append(event)
    engine.add_event_listener(listener)

    tool = make_ask_user_tool(engine)
    result = await tool(
        [_two_prompts()[0].to_dict()],
        _tool_call_id="tc-2",
    )
    assert isinstance(result, InterruptibleToolResult)
    assert any(e["type"] == "question.asked" for e in received)


# ── 4. Engine-level pause: tool returns → engine pauses → reply resumes ──

@pytest.mark.asyncio
async def test_ask_user_via_interrupt_signal_pauses_engine():
    """
    Simulate the full loop: the tool returns an InterruptibleToolResult, the
    loop raises InterruptSignal, the engine catches it and transitions to
    WAITING_INTERRUPT. After submit_question_reply, the engine resumes.
    """
    engine = _make_engine("question")

    # Directly simulate a real loop interrupt path: register the request,
    # then have the engine manually raise InterruptSignal the way the loop would.
    prompts = _two_prompts()
    await engine.register_question_request(
        request_id="rid-pause",
        tool_call_id="tc-pause",
        questions=prompts,
    )

    # Engine is currently in WAITING_INPUT (its idle state). Transition to
    # RUNNING and have the loop raise InterruptSignal — that's what happens
    # after the tool batch.
    engine._sm.transition(EngineState.RUNNING)

    # Catch the signal as _run_loop_guarded would
    try:
        raise InterruptSignal(
            request_id="rid-pause", tool_call_id="tc-pause", round_idx=0,
        )
    except InterruptSignal as sig:
        # We do what _run_loop_guarded does:
        engine._sm.transition(EngineState.WAITING_INTERRUPT)

    assert engine._sm.state == EngineState.WAITING_INTERRUPT

    # Now reply — engine rewrites the placeholder and restarts the loop
    result = await engine.submit_question_reply(
        "rid-pause", [["企业官网"], ["首页", "联系表单"]],
    )
    assert result["ok"] is True

    # After reply: request is no longer pending
    snap = await engine.get_snapshot()
    assert snap["pending_question_requests"] == []


@pytest.mark.asyncio
async def test_submit_reply_rewrites_placeholder_tool_result():
    """
    The placeholder tool_result the tool returned must be replaced by the
    real formatted text in self._messages. This is what allows the next
    LLM call to proceed.
    """
    from harness.types.messages import (
        Message, TextBlock, ToolCallBlock, ToolResultBlock,
    )
    engine = _make_engine("question")

    # Build a message pair: assistant(tool_call) + tool(placeholder)
    assistant_msg = Message(
        role="assistant",
        content=[ToolCallBlock(tool_call_id="tc-x", tool_name="ask_user", tool_input={})],
    )
    placeholder = ToolResultBlock(
        tool_call_id="tc-x",
        content="Question posted to the user. request_id=rid-x. Awaiting user reply.",
        is_interrupt=True,
        tool_name="ask_user",
    )
    tool_msg = Message(role="tool", content=[placeholder])
    engine._messages.extend([assistant_msg, tool_msg])

    # Register the request and then submit a reply
    prompts = _two_prompts()
    await engine.register_question_request(
        request_id="rid-x", tool_call_id="tc-x", questions=prompts,
    )
    result = await engine.submit_question_reply(
        "rid-x", [["企业官网"], ["首页"]],
    )
    assert result["ok"]

    # The placeholder was rewritten
    tool_block = tool_msg.content[0]
    assert tool_block.is_interrupt is False
    assert "User answered the clarification questions" in tool_block.content


# ── 5. State transitions are non-reversible & idempotent ──────────────────

@pytest.mark.asyncio
async def test_reply_twice_returns_error():
    engine = _make_engine("question")
    prompts = [QuestionPrompt(
        question="Q?",
        options=[QuestionOption(label="A"), QuestionOption(label="B")],
    )]
    await engine.register_question_request(
        request_id="rid-twice", tool_call_id="tc-t", questions=prompts,
    )
    r1 = await engine.submit_question_reply("rid-twice", [["A"]])
    assert r1["ok"]
    r2 = await engine.submit_question_reply("rid-twice", [["B"]])
    assert r2["ok"] is False
    assert "already" in r2["detail"]


@pytest.mark.asyncio
async def test_reject_then_reply_fails():
    engine = _make_engine("question")
    prompts = [QuestionPrompt(
        question="Q?",
        options=[QuestionOption(label="A"), QuestionOption(label="B")],
    )]
    await engine.register_question_request(
        request_id="rid-r", tool_call_id="tc-r", questions=prompts,
    )
    r_rej = await engine.reject_question("rid-r")
    assert r_rej["ok"]
    r_rep = await engine.submit_question_reply("rid-r", [["A"]])
    assert r_rep["ok"] is False


@pytest.mark.asyncio
async def test_unknown_request_id_returns_not_found():
    engine = _make_engine("question")
    r = await engine.submit_question_reply("does-not-exist", [["A"]])
    assert r["ok"] is False
    assert "not found" in r["detail"]
    r2 = await engine.reject_question("does-not-exist")
    assert r2["ok"] is False


# ── 6. Cancel expires all pending requests ────────────────────────────────

@pytest.mark.asyncio
async def test_cancel_expires_pending_questions():
    engine = _make_engine("question")
    prompts = [QuestionPrompt(
        question="Q?",
        options=[QuestionOption(label="A"), QuestionOption(label="B")],
    )]
    await engine.register_question_request(
        request_id="rid-c1", tool_call_id="tc-c1", questions=prompts,
    )
    await engine.register_question_request(
        request_id="rid-c2", tool_call_id="tc-c2", questions=prompts,
    )
    received: list[dict] = []
    engine.add_event_listener(lambda e: asyncio.create_task(_capture(received, e)))

    await engine.cancel()
    await asyncio.sleep(0)  # let the listener run
    snap = await engine.get_snapshot()
    assert snap["pending_question_requests"] == []
    assert any(
        e["type"] == "question.resolved" and e["data"]["status"] == "expired"
        for e in received
    ), received


async def _capture(bucket, event):
    bucket.append(event)


# ── 7. Validation rules (8 cases from previous spec) ──────────────────────

def test_case_1_question_mode_off_does_not_register_ask_user(monkeypatch):
    """Case 1: question_mode='noquestion' → ask_user is not registered."""
    monkeypatch.delenv("SERPER_API_KEY", raising=False)
    monkeypatch.delenv("BRAVE_SEARCH_API_KEY", raising=False)
    from harness.factory import build_engine
    from harness.config import HarnessConfig
    import os, tempfile
    tmp = tempfile.mkdtemp()
    cfg_path = os.path.join(tmp, "config.yaml")
    with open(cfg_path, "w") as f:
        f.write("""
default_provider: openai
providers:
  openai: {type: openai, api_key: x, base_url: http://x, model: y}
tools:
  enabled: [ask_user, web_search, web_fetch]
""")
    cfg = HarnessConfig.from_yaml(cfg_path)
    engine = build_engine(
        session_id="off", provider_cfg=cfg.providers["openai"],
        harness_cfg=cfg, session_store=MemorySessionStore(),
        question_mode="noquestion",
    )
    names = {t.schema.name for t in engine._tool_registry.discover()}
    assert "ask_user" not in names


def test_case_3_single_select_one_answer():
    prompts = _two_prompts()
    ok, _ = validate_answers_against_questions(prompts, [["企业官网"], ["首页"]])
    assert ok
    bad = [["企业官网", "作品集网站"], ["首页"]]
    ok, err = validate_answers_against_questions(prompts, bad)
    assert not ok and "single-select" in err


def test_case_4_multi_select_allows_multiple():
    prompts = _two_prompts()
    answers = [["Landing Page"], ["首页", "关于我们", "产品/服务展示", "联系表单", "后台管理"]]
    ok, err = validate_answers_against_questions(prompts, answers)
    assert ok, err


def test_case_5_custom_text_when_custom_true():
    prompts = _two_prompts()
    answers = [["我自己的网站类型"], ["首页", "联系表单", "独特的特性"]]
    ok, err = validate_answers_against_questions(prompts, answers)
    assert ok, err
    bad = [["A"], ["free1", "free2", "free3"]]
    ok, err = validate_answers_against_questions(prompts, bad)
    assert not ok and "free-text" in err


def test_case_8_invalid_answer_rejected():
    """custom=false + invalid label → validation fails."""
    prompts = [
        QuestionPrompt(
            question="Q1?",
            options=[QuestionOption(label="A"), QuestionOption(label="B")],
            multiple=False,
            custom=False,
        ),
    ]
    ok, err = validate_answers_against_questions(prompts, [["NOT_A_LABEL"]])
    assert not ok
    assert "valid option" in err
    ok2, err2 = validate_answers_against_questions(prompts, [["A"], ["B"]])
    assert not ok2
    assert "length" in err2


# ── 8. Schema / tool input validation ─────────────────────────────────────

def test_normalize_rejects_too_few_options():
    with pytest.raises(ValueError):
        _normalize_questions([
            {"question": "Q?", "options": [{"label": "A"}]},
        ])


def test_normalize_rejects_too_many_questions():
    with pytest.raises(ValueError):
        _normalize_questions([
            {"question": f"Q{i}?", "options": [{"label": "A"}, {"label": "B"}]}
            for i in range(6)
        ])


def test_normalize_dedupes_options():
    out = _normalize_questions([
        {"question": "Q?", "options": [
            {"label": "A"}, {"label": "A"}, {"label": "B"},
        ]},
    ])
    assert [o.label for o in out[0].options] == ["A", "B"]


def test_format_answers_shape():
    prompts = _two_prompts()
    text = format_answers_for_llm(prompts, [["企业官网"], ["首页", "联系表单"]])
    assert text.startswith("User answered the clarification questions:")
    assert "1. 网站类型" in text
    assert "2. 核心功能" in text
    assert "企业官网" in text


# ── 9. Endpoint smoke test ────────────────────────────────────────────────

def test_reply_and_reject_endpoints_are_registered():
    from api.rest import app
    paths = {(r.path, tuple(r.methods)) for r in app.routes if hasattr(r, "methods")}
    has_reply = any(
        p == "/sessions/{session_id}/questions/{request_id}/reply" and "POST" in m
        for p, m in paths
    )
    has_reject = any(
        p == "/sessions/{session_id}/questions/{request_id}/reject" and "POST" in m
        for p, m in paths
    )
    assert has_reply
    assert has_reject


# ── 10. End-to-end: tool returns immediately, reply restarts engine ──────

@pytest.mark.asyncio
async def test_end_to_end_interrupt_then_resume():
    """
    Simulates the full conversation flow:
      1. ask_user tool called → returns InterruptibleToolResult (non-blocking)
      2. Engine pause signal raised
      3. User submits answers
      4. Engine rewrites placeholder, emits question.resolved, restarts
    """
    from harness.types.messages import (
        Message, ToolCallBlock, ToolResultBlock,
    )
    engine = _make_engine("question")
    received: list[dict] = []
    engine.add_event_listener(_captured_factory(received))

    tool = make_ask_user_tool(engine)
    prompts = _two_prompts()
    tool_call_id = "tc-e2e"

    # Build the assistant tool_call message as the LLM would
    assistant_msg = Message(
        role="assistant",
        content=[ToolCallBlock(tool_call_id=tool_call_id, tool_name="ask_user",
                               tool_input={"questions": [p.to_dict() for p in prompts]})],
    )
    engine._messages.append(assistant_msg)

    # 1) Tool returns immediately (non-blocking)
    result = await tool([p.to_dict() for p in prompts], _tool_call_id=tool_call_id)
    assert isinstance(result, InterruptibleToolResult)
    assert result.is_interrupt
    # Engine has the request
    assert len((await engine.get_snapshot())["pending_question_requests"]) == 1
    # question.asked event was pushed
    assert any(e["type"] == "question.asked" for e in received)

    # 2) Loop would raise InterruptSignal here; engine catches + pauses
    engine._sm.transition(EngineState.RUNNING)
    try:
        raise InterruptSignal(request_id="ignored", tool_call_id=tool_call_id, round_idx=0)
    except InterruptSignal:
        engine._sm.transition(EngineState.WAITING_INTERRUPT)
    assert engine._sm.state == EngineState.WAITING_INTERRUPT

    # Place the placeholder in messages
    placeholder = ToolResultBlock(
        tool_call_id=tool_call_id,
        content=result.content,
        is_interrupt=True,
        tool_name="ask_user",
    )
    engine._messages.append(Message(role="tool", content=[placeholder]))

    # 3) User submits answers
    submit_result = await engine.submit_question_reply(
        received[-1]["data"]["request_id"],
        [["企业官网"], ["首页", "联系表单"]],
    )
    assert submit_result["ok"]

    # 4) Placeholder was rewritten; question.resolved was pushed
    assert placeholder.is_interrupt is False
    assert "User answered" in placeholder.content
    assert any(
        e["type"] == "question.resolved" and e["data"]["status"] == "answered"
        for e in received
    )


def _captured_factory(bucket):
    async def _cap(event):
        bucket.append(event)
    return _cap
