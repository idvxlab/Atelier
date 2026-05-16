"""Tests for spawn_agent / spawn_agents tools and AgentEngine.run_to_completion()."""
from __future__ import annotations

import asyncio
import pytest

from harness.engine.engine import AgentEngine, EngineConfig
from harness.engine.loop import ReactLoop
from harness.engine.compression import CompressionConfig, ContextCompressor
from harness.engine.state_machine import EngineState
from harness.observability.events import EventEmitter
from harness.storage.backends.memory import MemorySessionStore
from harness.tools.executor import ToolExecutor
from harness.tools.overflow import OverflowStore
from harness.tools.registry import ToolRegistry
from harness.tools.builtin.spawn_agent import (
    MAX_SPAWN_DEPTH,
    make_spawn_agent_tool,
    make_spawn_agents_tool,
)
from harness.types.messages import Message, TextBlock


# ── Shared mock helpers ────────────────────────────────────────────────────────

class _MockLLM:
    """Returns a configurable fixed text reply with no tool calls."""
    def __init__(self, reply_text: str = "Done.") -> None:
        self._text = reply_text

    async def chat(self, messages, tools=None):
        return Message(role="assistant", content=[TextBlock(text=self._text)])

    async def stream_chat(self, messages, tools=None, on_token=None):
        if on_token:
            for word in self._text.split():
                await on_token(word + " ")
        return await self.chat(messages, tools)

    async def complete(self, prompt: str) -> str:
        return "Summary."


def _build_engine(reply_text: str = "Done.", session_id: str = "test") -> AgentEngine:
    emitter = EventEmitter(session_id)
    llm = _MockLLM(reply_text)
    store = MemorySessionStore()
    registry = ToolRegistry()
    overflow = OverflowStore()
    executor = ToolExecutor(registry=registry, overflow=overflow, emitter=emitter)
    compressor = ContextCompressor(summarizer=llm, config=CompressionConfig())
    loop = ReactLoop(
        llm=llm,
        tool_registry=registry,
        tool_executor=executor,
        compressor=compressor,
        emitter=emitter,
        max_rounds=5,
    )
    return AgentEngine(
        config=EngineConfig(session_id=session_id),
        loop=loop,
        session_store=store,
        emitter=emitter,
        tool_registry=registry,
    )


# ── run_to_completion() ────────────────────────────────────────────────────────

class TestRunToCompletion:
    @pytest.mark.asyncio
    async def test_returns_last_assistant_text(self):
        engine = _build_engine("The answer is 42.")
        result = await engine.run_to_completion("What is the answer?")
        assert result == "The answer is 42."

    @pytest.mark.asyncio
    async def test_engine_reaches_completed_state(self):
        engine = _build_engine("Done.")
        await engine.run_to_completion("Go.")
        snap = await engine.get_snapshot()
        assert snap["state"] == "COMPLETED"
        assert not snap["is_running"]

    @pytest.mark.asyncio
    async def test_messages_contain_user_and_assistant(self):
        engine = _build_engine("Hi!")
        await engine.run_to_completion("Hello")
        snap = await engine.get_snapshot()
        roles = [m["role"] for m in snap["last_messages"]]
        assert "user" in roles
        assert "assistant" in roles

    @pytest.mark.asyncio
    async def test_no_response_fallback(self):
        """Engine that returns empty text → fallback string."""
        engine = _build_engine("")
        result = await engine.run_to_completion("ping")
        # empty TextBlock text → falls through to fallback
        assert result == "(no response)"

    @pytest.mark.asyncio
    async def test_can_reuse_after_completion(self):
        """run_to_completion on a fresh engine; state machine should allow it."""
        engine = _build_engine("First.")
        r1 = await engine.run_to_completion("First task")
        assert r1 == "First."
        # Reuse: state goes COMPLETED → WAITING_INPUT → RUNNING via send_message
        await engine.send_message("Second task")
        await asyncio.sleep(0.05)
        snap = await engine.get_snapshot()
        assert snap["state"] == "COMPLETED"


# ── spawn_agent tool ───────────────────────────────────────────────────────────

class _FakeHarnessCfg:
    """Minimal stand-in for HarnessConfig used by spawn tool factories."""
    class compression:
        token_window = 128_000
        auto_trigger_ratio = 0.65
        micro_keep_recent = 6
        summary_provider = ""

    class engine:
        max_rounds = 5

    class tools:
        enabled = None
        limits: dict = {}

    providers: dict = {}
    mcp_servers: dict = {}


class _FakeProviderCfg:
    name = "openai-compatible"
    model = "mock"
    api_key = ""
    base_url = ""
    timeout = 10.0
    max_tokens = 256
    temperature = 0.0
    extra: dict = {}


def _make_mock_build_engine(reply_text: str):
    """Return a build_engine replacement that always uses _MockLLM."""
    def _build(session_id, provider_cfg, harness_cfg, session_store,
                system_prompt="", allowed_tools=None, registry=None, spawn_depth=0):
        return _build_engine(reply_text=reply_text, session_id=session_id)
    return _build


class TestSpawnAgentTool:
    @pytest.mark.asyncio
    async def test_returns_sub_agent_response(self, monkeypatch):
        """spawn_agent_tool runs a sub-engine and returns its text."""
        import harness.tools.builtin.spawn_agent as sa_mod
        monkeypatch.setattr(
            "harness.factory.build_engine",
            _make_mock_build_engine("Sub result."),
        )
        tool = make_spawn_agent_tool(
            harness_cfg=_FakeHarnessCfg(),
            provider_cfg=_FakeProviderCfg(),
            session_store=MemorySessionStore(),
            spawn_depth=0,
        )
        result = await tool(task="Do something")
        assert result == "Sub result."

    @pytest.mark.asyncio
    async def test_depth_limit_returns_error_string(self):
        """At MAX_SPAWN_DEPTH, returns an error string instead of spawning."""
        tool = make_spawn_agent_tool(
            harness_cfg=_FakeHarnessCfg(),
            provider_cfg=_FakeProviderCfg(),
            session_store=MemorySessionStore(),
            spawn_depth=MAX_SPAWN_DEPTH,  # already at limit
        )
        result = await tool(task="Should not run")
        assert "maximum" in result.lower()
        assert "depth" in result.lower()

    @pytest.mark.asyncio
    async def test_sub_agent_exception_returns_error_string(self, monkeypatch):
        """If sub-engine raises, the tool returns an error string (never raises)."""
        def _failing_build(**kwargs):
            raise RuntimeError("provider down")

        monkeypatch.setattr("harness.factory.build_engine", _failing_build)
        tool = make_spawn_agent_tool(
            harness_cfg=_FakeHarnessCfg(),
            provider_cfg=_FakeProviderCfg(),
            session_store=MemorySessionStore(),
            spawn_depth=0,
        )
        result = await tool(task="Will fail")
        assert result.startswith("Error:")


# ── spawn_agents tool ──────────────────────────────────────────────────────────

class TestSpawnAgentsTool:
    @pytest.mark.asyncio
    async def test_parallel_results_all_present(self, monkeypatch):
        """All sub-agent results appear in the combined output."""
        call_count = 0

        async def _fake_run_to_completion(self_engine, task):
            nonlocal call_count
            call_count += 1
            return f"result_for_{task}"

        monkeypatch.setattr(AgentEngine, "run_to_completion", _fake_run_to_completion)
        monkeypatch.setattr(
            "harness.factory.build_engine",
            _make_mock_build_engine("ignored"),
        )
        tool = make_spawn_agents_tool(
            harness_cfg=_FakeHarnessCfg(),
            provider_cfg=_FakeProviderCfg(),
            session_store=MemorySessionStore(),
            spawn_depth=0,
        )
        result = await tool(agents=[
            {"task": "alpha"},
            {"task": "beta"},
            {"task": "gamma"},
        ])
        assert call_count == 3
        assert "result_for_alpha" in result
        assert "result_for_beta" in result
        assert "result_for_gamma" in result

    @pytest.mark.asyncio
    async def test_empty_agents_list_returns_error(self):
        tool = make_spawn_agents_tool(
            harness_cfg=_FakeHarnessCfg(),
            provider_cfg=_FakeProviderCfg(),
            session_store=MemorySessionStore(),
            spawn_depth=0,
        )
        result = await tool(agents=[])
        assert result.startswith("Error:")

    @pytest.mark.asyncio
    async def test_depth_limit_returns_error_string(self):
        tool = make_spawn_agents_tool(
            harness_cfg=_FakeHarnessCfg(),
            provider_cfg=_FakeProviderCfg(),
            session_store=MemorySessionStore(),
            spawn_depth=MAX_SPAWN_DEPTH,
        )
        result = await tool(agents=[{"task": "nope"}])
        assert "maximum" in result.lower()

    @pytest.mark.asyncio
    async def test_results_separated_by_divider(self, monkeypatch):
        """Multiple results are joined with the '---' divider."""
        async def _fake_run(self_engine, task):
            return f"answer:{task}"

        monkeypatch.setattr(AgentEngine, "run_to_completion", _fake_run)
        monkeypatch.setattr(
            "harness.factory.build_engine",
            _make_mock_build_engine("ignored"),
        )
        tool = make_spawn_agents_tool(
            harness_cfg=_FakeHarnessCfg(),
            provider_cfg=_FakeProviderCfg(),
            session_store=MemorySessionStore(),
            spawn_depth=0,
        )
        result = await tool(agents=[{"task": "A"}, {"task": "B"}])
        assert "---" in result
