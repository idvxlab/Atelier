"""Tests for the engine state machine and AgentEngine."""
from __future__ import annotations

import asyncio
import pytest

from harness.engine.state_machine import (
    EngineState,
    IllegalTransitionError,
    StateMachine,
)
from harness.engine.engine import AgentEngine, EngineConfig
from harness.engine.loop import ReactLoop
from harness.engine.compression import CompressionConfig, ContextCompressor
from harness.engine.loop_detector import LoopDetector
from harness.types.messages import Message, TextBlock, ToolCallBlock, ToolResultBlock
from harness.observability.events import EventEmitter
from harness.tools.executor import ToolExecutor
from harness.tools.registry import ToolRegistry
from harness.tools.overflow import OverflowStore
from harness.storage.backends.memory import MemorySessionStore


# ──────────────────────────────────────────────────────────────────────
# StateMachine
# ──────────────────────────────────────────────────────────────────────

class TestStateMachine:
    def test_initial_state(self):
        sm = StateMachine()
        assert sm.state == EngineState.WAITING_INPUT

    def test_legal_transition(self):
        sm = StateMachine()
        sm.transition(EngineState.RUNNING)
        assert sm.state == EngineState.RUNNING

    def test_illegal_transition_raises(self):
        sm = StateMachine()
        with pytest.raises(IllegalTransitionError):
            sm.transition(EngineState.COMPLETED)  # must go through RUNNING first

    def test_full_happy_path(self):
        sm = StateMachine()
        sm.transition(EngineState.RUNNING)
        sm.transition(EngineState.COMPLETED)
        # Session reuse
        sm.transition(EngineState.WAITING_INPUT)
        assert sm.state == EngineState.WAITING_INPUT

    def test_error_recovery(self):
        sm = StateMachine()
        sm.transition(EngineState.RUNNING)
        sm.transition(EngineState.ERROR)
        sm.transition(EngineState.WAITING_INPUT)
        assert sm.state == EngineState.WAITING_INPUT

    def test_cancel_goes_to_waiting_not_error(self):
        sm = StateMachine()
        sm.transition(EngineState.RUNNING)
        sm.transition(EngineState.WAITING_INPUT)  # cancel path
        assert sm.state == EngineState.WAITING_INPUT


# ──────────────────────────────────────────────────────────────────────
# LoopDetector
# ──────────────────────────────────────────────────────────────────────

class TestLoopDetector:
    def _make_calls(self, *names: str) -> list[ToolCallBlock]:
        return [
            ToolCallBlock(tool_call_id=f"id-{n}", tool_name=n, tool_input={})
            for n in names
        ]

    def test_no_repeat_initially(self):
        ld = LoopDetector(window=5, threshold=2)
        assert not ld.is_repeated(self._make_calls("read_file"))

    def test_detects_repeat_on_second_occurrence(self):
        ld = LoopDetector(window=5, threshold=2)
        ld.is_repeated(self._make_calls("shell"))   # first — not repeated
        assert ld.is_repeated(self._make_calls("shell"))  # second — repeated!

    def test_different_tools_not_repeated(self):
        ld = LoopDetector(window=5, threshold=2)
        ld.is_repeated(self._make_calls("read_file"))
        assert not ld.is_repeated(self._make_calls("shell"))

    def test_window_eviction(self):
        ld = LoopDetector(window=3, threshold=2)
        ld.is_repeated(self._make_calls("shell"))
        ld.is_repeated(self._make_calls("a"))
        ld.is_repeated(self._make_calls("b"))
        ld.is_repeated(self._make_calls("c"))
        # "shell" was evicted from the window (size 3), so not repeated
        assert not ld.is_repeated(self._make_calls("shell"))


# ──────────────────────────────────────────────────────────────────────
# AgentEngine integration
# ──────────────────────────────────────────────────────────────────────

class _MockLLM:
    """Returns a fixed text reply with no tool calls."""
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


def _build_engine(reply_text: str = "Done.") -> AgentEngine:
    session_id = "test-engine"
    emitter = EventEmitter(session_id)
    llm = _MockLLM(reply_text)
    store = MemorySessionStore()
    registry = ToolRegistry()
    overflow = OverflowStore()
    executor = ToolExecutor(registry=registry, overflow=overflow, emitter=emitter)
    compressor = ContextCompressor(
        summarizer=llm,
        config=CompressionConfig(),
    )
    loop = ReactLoop(
        llm=llm,
        tool_registry=registry,
        tool_executor=executor,
        compressor=compressor,
        emitter=emitter,
        max_rounds=10,
    )
    return AgentEngine(
        config=EngineConfig(session_id=session_id),
        loop=loop,
        session_store=store,
        emitter=emitter,
    )


@pytest.mark.asyncio
async def test_engine_completes_on_text_reply():
    engine = _build_engine("The answer is 42.")
    await engine.send_message("What is the answer?")
    await asyncio.sleep(0.1)  # let the task run
    snapshot = await engine.get_snapshot()
    assert snapshot["state"] == "COMPLETED"
    assert not snapshot["is_running"]
    # Last message should be the assistant reply
    last = snapshot["last_messages"][-1]
    assert last["role"] == "assistant"


@pytest.mark.asyncio
async def test_engine_cancel():
    class _SlowLLM:
        async def chat(self, messages, tools=None):
            await asyncio.sleep(10)  # blocks until cancelled
            return Message(role="assistant", content=[TextBlock(text="Never")])
        async def stream_chat(self, messages, tools=None, on_token=None):
            return await self.chat(messages, tools)
        async def complete(self, prompt):
            return ""

    session_id = "cancel-test"
    emitter = EventEmitter(session_id)
    llm = _SlowLLM()
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
    engine = AgentEngine(
        config=EngineConfig(session_id=session_id),
        loop=loop,
        session_store=store,
        emitter=emitter,
    )

    await engine.send_message("Start.")
    await asyncio.sleep(0.05)
    await engine.cancel()
    await asyncio.sleep(0.2)
    snapshot = await engine.get_snapshot()
    # After cancel, engine goes back to WAITING_INPUT (not ERROR)
    assert snapshot["state"] == "WAITING_INPUT"


@pytest.mark.asyncio
async def test_engine_session_reuse():
    engine = _build_engine("Reply.")
    await engine.send_message("First message.")
    await asyncio.sleep(0.1)
    assert (await engine.get_snapshot())["state"] == "COMPLETED"

    await engine.send_message("Second message.")
    await asyncio.sleep(0.1)
    assert (await engine.get_snapshot())["state"] == "COMPLETED"
