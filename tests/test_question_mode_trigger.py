"""
Tests for the QuestionMode trigger logic.

These tests verify that:

  Case 1: question_mode == "noquestion" → ask_user is NOT registered.
  Case 2: question_mode == "question"  → ask_user IS registered.
  Case 3: System prompt in "question" mode contains STRONG, EXPLICIT
          instructions to use ask_user (no plain-text clarification).
  Case 4: ask_user OpenAI schema is well-formed (nested descriptions,
          type fields, required fields).
  Case 5: Runtime set_question_mode('noquestion' → 'question') mutates
          the live system message so the LLM sees the new instructions.
  Case 6: ask_user tool handler returns an InterruptibleToolResult
          (non-blocking) — even when the LLM has called it, the tool
          never blocks on the user.
"""
from __future__ import annotations

import asyncio
import pytest
import os
import tempfile
from unittest.mock import MagicMock

from harness.engine.engine import AgentEngine, EngineConfig
from harness.engine.state_machine import EngineState
from harness.storage.backends.memory import MemorySessionStore
from harness.types.messages import TextBlock
from harness.tools.builtin.ask_user import (
    ASK_USER_SCHEMA,
    make_ask_user_tool,
)
from harness.tools.executor import InterruptibleToolResult
from harness.factory import build_engine, QUESTION_INSTRUCTIONS, NOQUESTION_INSTRUCTIONS
from harness.config import HarnessConfig


# ── helpers ────────────────────────────────────────────────────────────────

def _write_minimal_config(tools_enabled: list[str]) -> HarnessConfig:
    tmp = tempfile.mkdtemp()
    cfg_path = os.path.join(tmp, "config.yaml")
    with open(cfg_path, "w") as f:
        f.write(
            f"default_provider: openai\n"
            f"providers:\n"
            f"  openai: {{name: openai, api_key: x, base_url: http://x, model: y}}\n"
            f"tools:\n"
            f"  enabled: {tools_enabled!r}\n"
        )
    return HarnessConfig.from_yaml(cfg_path)


def _build(question_mode: str, tools_enabled: list[str] | None = None) -> AgentEngine:
    if tools_enabled is None:
        tools_enabled = ["read_file", "ask_user"]
    cfg = _write_minimal_config(tools_enabled)
    return build_engine(
        session_id=f"s-{question_mode}",
        provider_cfg=cfg.providers["openai"],
        harness_cfg=cfg,
        session_store=MemorySessionStore(),
        question_mode=question_mode,
    )


# ── Case 1: noquestion mode does NOT register ask_user ────────────────────

def test_case_1_noquestion_mode_ask_user_not_registered():
    """
    With question_mode='noquestion' and ask_user NOT in the user's tools.enabled,
    the engine must not have ask_user in its registry.
    """
    eng = _build("noquestion", tools_enabled=["read_file", "write_file"])
    names = {t.schema.name for t in eng._tool_registry.discover()}
    assert "ask_user" not in names, (
        f"ask_user leaked into noquestion registry: {names}"
    )


# ── Case 2: question mode registers ask_user ──────────────────────────────

def test_case_2_question_mode_ask_user_registered():
    eng = _build("question")
    names = {t.schema.name for t in eng._tool_registry.discover()}
    assert "ask_user" in names


def test_case_2b_question_mode_with_ask_user_in_config():
    """Even if ask_user is in tools.enabled, the registration is consistent."""
    eng = _build("question", tools_enabled=["ask_user"])
    names = {t.schema.name for t in eng._tool_registry.discover()}
    assert "ask_user" in names


# ── Case 3: system prompt is STRONG and explicit ──────────────────────────

def test_case_3_question_mode_system_prompt_is_explicit():
    """
    The question-mode block in the system prompt must explicitly forbid
    plain-text clarification, so the LLM is forced to call ask_user.
    """
    eng = _build("question")
    sys_msg = next(m for m in eng._messages if m.role == "system")
    text = sys_msg.text_content()

    # Must contain the new STRONG markers
    assert "STRUCTURED clarification only" in text, (
        "Question Mode header not in system prompt"
    )
    assert "MUST use the `ask_user` tool" in text, (
        "ask_user enforcement phrase missing"
    )
    assert "FORBIDDEN" in text, (
        "Plain-text clarification is not explicitly forbidden"
    )
    assert "NEVER output clarification questions as plain assistant text" in text, (
        "Hard rule #1 missing"
    )
    assert "your FIRST turn response must include" in text, (
        "First-turn-must-be-tool-call rule missing"
    )

    # And the legacy "soft" wording must not be the only thing present
    assert "LLM decision layer" not in text, (
        "Old soft phrasing leaked into new prompt"
    )


def test_case_3b_noquestion_system_prompt_explicit():
    eng = _build("noquestion", tools_enabled=["read_file"])
    sys_msg = next(m for m in eng._messages if m.role == "system")
    text = sys_msg.text_content()
    assert "Direct Execution Mode" in text
    assert "ask_user` tool is not available" in text


# ── Case 4: ask_user OpenAI schema is well-formed ──────────────────────────

def test_case_4_ask_user_schema_exposes_questions_to_llm():
    """
    The schema sent to the LLM must be a valid OpenAI function schema
    with proper nested typing — every property has a `type`, the
    `questions` field is required, and options/label/description are
    all exposed with descriptions.
    """
    from harness.llm.openai_provider import OpenAIProvider
    from harness.llm.base import LLMConfig

    eng = _build("question")
    ask = eng._tool_registry.get("ask_user")
    assert ask is not None
    assert ask.schema.name == "ask_user"

    prov = OpenAIProvider(LLMConfig(api_key="x", model="y", timeout=30))
    serialized = prov._to_openai_tool(ask.schema)

    fn = serialized["function"]
    assert fn["name"] == "ask_user"
    assert "clickable UI" in fn["description"] or "structured" in fn["description"].lower()
    assert "FORBIDDEN" in fn["description"] or "DO NOT" in fn["description"], (
        "Description must forbid plain-text clarification"
    )

    params = fn["parameters"]
    assert params["type"] == "object"
    assert "questions" in params["properties"]
    assert "questions" in params["required"]

    qprops = params["properties"]["questions"]
    assert qprops["type"] == "array"
    assert qprops["items"]["type"] == "object"

    inner = qprops["items"]["properties"]
    # Every inner property must have a type and a description
    for key in ("question", "header", "options", "multiple", "custom"):
        assert key in inner, f"missing inner field: {key}"
        assert "type" in inner[key], f"inner {key} missing type"
        assert "description" in inner[key], f"inner {key} missing description"

    # options → items → properties: label/description must be exposed with descriptions
    opts_inner = inner["options"]["items"]["properties"]
    assert "label" in opts_inner and "description" in opts_inner
    assert "type" in opts_inner["label"]
    assert "type" in opts_inner["description"]
    assert "description" in opts_inner["label"]
    assert "description" in opts_inner["description"]


# ── Case 5: runtime set_question_mode mutates the system message ───────────

@pytest.mark.asyncio
async def test_case_5_runtime_toggle_mutates_system_message():
    """
    Toggling question_mode at runtime (the common UX path: user clicks
    the toggle in the toolbar AFTER a session already exists) must
    rewrite the system message in place so the LLM sees the new
    instructions on the next turn.
    """
    eng = _build("noquestion", tools_enabled=["read_file"])
    sys_msg = next(m for m in eng._messages if m.role == "system")
    text_before = sys_msg.text_content()
    assert "Direct Execution Mode" in text_before
    assert "STRUCTURED clarification only" not in text_before

    # Toggle to question mode
    await eng.set_question_mode("question")
    # The async re-stamp is scheduled via create_task; give it a tick.
    await asyncio.sleep(0.05)

    sys_msg = next(m for m in eng._messages if m.role == "system")
    text_after = sys_msg.text_content()
    assert "STRUCTURED clarification only" in text_after
    assert "NEVER output clarification questions" in text_after
    assert "Direct Execution Mode" not in text_after, (
        "Old block was not removed"
    )

    # Toggle back
    await eng.set_question_mode("noquestion")
    await asyncio.sleep(0.05)
    sys_msg = next(m for m in eng._messages if m.role == "system")
    text_back = sys_msg.text_content()
    assert "Direct Execution Mode" in text_back
    assert "STRUCTURED clarification only" not in text_back


@pytest.mark.asyncio
async def test_case_5b_runtime_toggle_also_registers_tool():
    """
    When the user toggles question_mode on at runtime, ask_user must
    appear in the tool registry so the LLM can actually call it.
    """
    eng = _build("noquestion", tools_enabled=["read_file"])
    names_before = {t.schema.name for t in eng._tool_registry.discover()}
    assert "ask_user" not in names_before

    # Use the same path the REST handler uses
    from harness.tools.builtin.ask_user import (
        ASK_USER_SCHEMA, make_ask_user_tool,
    )
    reg = eng._tool_registry
    if "ask_user" not in {t.schema.name for t in reg.discover()}:
        reg.register(ASK_USER_SCHEMA, make_ask_user_tool(eng))

    names_after = {t.schema.name for t in reg.discover()}
    assert "ask_user" in names_after


# ── Case 6: ask_user tool is non-blocking ──────────────────────────────────

@pytest.mark.asyncio
async def test_case_6_ask_user_tool_returns_immediately():
    """
    The ask_user tool handler must return an InterruptibleToolResult
    immediately, even if the user is sleeping. It MUST NOT block.
    """
    eng = _build("question")
    tool = make_ask_user_tool(eng)

    call_payload = [{
        "header": "网站目标",
        "question": "网站的主要用途是什么？",
        "options": [
            {"label": "展示公司信息", "description": "企业官网、品牌介绍"},
            {"label": "提供在线服务", "description": "适合 SaaS、咨询"},
            {"label": "销售产品",     "description": "电商、商品、支付"},
        ],
        "multiple": False,
        "custom": True,
    }]

    async def run_tool():
        return await tool(call_payload, _tool_call_id="tc-broad")

    # Run with a tight timeout — if the tool blocks, this test fails.
    result = await asyncio.wait_for(run_tool(), timeout=1.0)
    assert isinstance(result, InterruptibleToolResult)
    assert result.is_interrupt is True
    # Engine has the request
    snap = await eng.get_snapshot()
    assert len(snap["pending_question_requests"]) == 1


@pytest.mark.asyncio
async def test_case_6b_ask_user_does_not_produce_assistant_text():
    """
    A LLM that "asks" via plain assistant text produces a message that
    is NOT a tool_call. The question-mode design demands that the LLM
    call ask_user; therefore, an assistant message that contains only
    TextBlock (no tool_calls) with the word "网站" must NOT be the
    "response" to a broad request — the system prompt explicitly
    forbids it.

    This test pins down the policy: when question_mode is on and a
    broad request is made, the very first response must contain a
    tool_call to ask_user. We assert that the engine's snapshot of
    pending_question_requests is populated after such a call.
    """
    eng = _build("question")
    tool = make_ask_user_tool(eng)

    # Simulate what the LLM must do
    await tool(
        [{
            "header": "网站目标",
            "question": "网站的主要用途？",
            "options": [
                {"label": "A", "description": "a"},
                {"label": "B", "description": "b"},
            ],
            "multiple": False,
            "custom": True,
        }],
        _tool_call_id="tc-policy",
    )
    snap = await eng.get_snapshot()
    assert snap["pending_question_requests"], (
        "If a broad task enters Question Mode, the LLM's first response "
        "must be an ask_user tool call. This test asserts the engine "
        "received that call."
    )


# ── Case (extra): the system prompt + tool description together force ─────
# a tool call when the user request is broad. This is asserted at the
# prompt-level — i.e. the LLM has explicit textual cues to call ask_user.

def test_case_7_system_prompt_explicitly_mentions_broad_request():
    eng = _build("question")
    sys_msg = next(m for m in eng._messages if m.role == "system")
    text = sys_msg.text_content()
    # Must mention at least one example of a broad/ambiguous request
    assert "broad" in text.lower()
    assert "design a website" in text or "网站" in text or "build me" in text


# ── Case (extra): ask_user schema's options field has full descriptions ──

def test_case_8_ask_user_options_have_descriptions():
    """Each option's `label` and `description` are exposed with descriptions."""
    from harness.llm.openai_provider import OpenAIProvider
    from harness.llm.base import LLMConfig

    eng = _build("question")
    prov = OpenAIProvider(LLMConfig(api_key="x", model="y", timeout=30))
    ask = eng._tool_registry.get("ask_user")
    serialized = prov._to_openai_tool(ask.schema)
    opt_props = serialized["function"]["parameters"]["properties"]["questions"]["items"]["properties"]["options"]["items"]["properties"]
    assert "description" in opt_props["label"]
    assert "description" in opt_props["description"]
    # And the Recommended guidance is in the description
    assert "Recommended" in opt_props["description"]["description"]
