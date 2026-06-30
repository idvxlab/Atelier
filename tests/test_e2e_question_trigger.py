"""End-to-end smoke test for Question Mode trigger logic.

Simulates the user's reported scenario: "请你帮我设计一个网站" → broad
request → LLM must call ask_user → tool returns InterruptibleToolResult →
engine parks in WAITING_INTERRUPT → WS event question.asked → user
submits answers → engine resumes.
"""
from __future__ import annotations
from harness.factory import build_engine
from harness.config import HarnessConfig
from harness.storage.backends.memory import MemorySessionStore
from harness.engine.engine import EngineState
from harness.tools.builtin.ask_user import make_ask_user_tool
from harness.types.messages import Message, ToolCallBlock
import os, tempfile, asyncio


def _build_question_session():
    tmp = tempfile.mkdtemp()
    cfg_path = os.path.join(tmp, "config.yaml")
    with open(cfg_path, "w") as f:
        f.write(
            "default_provider: openai\n"
            "providers:\n"
            "  openai: {name: openai, api_key: x, base_url: http://x, model: y}\n"
            "tools:\n"
            "  enabled: [read_file, ask_user]\n"
        )
    cfg = HarnessConfig.from_yaml(cfg_path)
    return build_engine(
        session_id="website",
        provider_cfg=cfg.providers["openai"],
        harness_cfg=cfg,
        session_store=MemorySessionStore(),
        question_mode="question",
    )


def test_ask_user_is_registered_and_prompt_is_strong():
    eng = _build_question_session()
    names = [t.schema.name for t in eng._tool_registry.discover()]
    assert "ask_user" in names

    sys_msg = next(m for m in eng._messages if m.role == "system")
    text = sys_msg.text_content()
    assert "NEVER output clarification questions as plain assistant text" in text


def test_broad_request_path_full_flow():
    eng = _build_question_session()

    # Simulate the assistant's first response: a tool_call to ask_user
    eng._messages.append(
        Message(
            role="assistant",
            content=[ToolCallBlock(
                tool_call_id="call_1", tool_name="ask_user",
                tool_input={"questions": "see below"},
            )],
        )
    )

    events = []
    async def listener(e):
        events.append(e)
    eng.add_event_listener(listener)

    tool = make_ask_user_tool(eng)
    questions_payload = [{
        "header": "网站目标",
        "question": "网站的主要用途是什么？",
        "options": [
            {"label": "展示公司信息", "description": "企业官网 · Recommended"},
            {"label": "提供在线服务", "description": "SaaS、咨询"},
            {"label": "销售产品", "description": "电商、商品"},
            {"label": "作品/案例展示", "description": "作品集"},
        ],
        "multiple": False,
        "custom": True,
    }]

    async def run_tool():
        return await tool(questions_payload, _tool_call_id="call_1")

    result = asyncio.run(run_tool())

    # Tool is non-blocking
    from harness.tools.executor import InterruptibleToolResult
    assert isinstance(result, InterruptibleToolResult)
    assert result.is_interrupt

    # Engine registered the question
    snap = asyncio.run(eng.get_snapshot())
    assert len(snap["pending_question_requests"]) == 1

    # WS event question.asked was pushed
    assert any(e["type"] == "question.asked" for e in events)

    # Engine can transition to WAITING_INTERRUPT (simulating loop interrupt)
    eng._sm.transition(EngineState.RUNNING)
    eng._sm.transition(EngineState.WAITING_INTERRUPT)
    assert eng._sm.state == EngineState.WAITING_INTERRUPT

    # User submits answers
    reply = asyncio.run(eng.submit_question_reply(
        events[-1]["data"]["request_id"],
        [["展示公司信息"]],
    ))
    assert reply["ok"]

    # question.resolved was pushed
    assert any(e["type"] == "question.resolved" for e in events)


def test_noquestion_mode_does_not_register_ask_user():
    eng = _build_question_session()  # uses question mode
    # Manually build a noquestion engine to compare
    tmp = tempfile.mkdtemp()
    cfg_path = os.path.join(tmp, "config.yaml")
    with open(cfg_path, "w") as f:
        f.write(
            "default_provider: openai\n"
            "providers:\n"
            "  openai: {name: openai, api_key: x, base_url: http://x, model: y}\n"
            "tools:\n"
            "  enabled: [read_file, write_file]\n"
        )
    cfg = HarnessConfig.from_yaml(cfg_path)
    eng_nq = build_engine(
        session_id="nq",
        provider_cfg=cfg.providers["openai"],
        harness_cfg=cfg,
        session_store=MemorySessionStore(),
        question_mode="noquestion",
    )
    names = {t.schema.name for t in eng_nq._tool_registry.discover()}
    assert "ask_user" not in names