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
        tool_registry=registry,
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
        tool_registry=registry,
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


@pytest.mark.asyncio
async def test_engine_recovers_from_error_on_send_message():
    """
    After a loop error, the engine should be in ERROR state.
    The next send_message() must NOT raise IllegalTransitionError;
    it should silently transition ERROR -> WAITING_INPUT -> RUNNING.
    """
    engine = _build_engine("Will fail first, then succeed.")

    # Manually drive the state machine to ERROR (simulating an upstream 400)
    from harness.engine.state_machine import StateMachine
    engine._sm.transition(EngineState.RUNNING)
    engine._sm.transition(EngineState.ERROR)
    assert engine._sm.state == EngineState.ERROR

    # The next user message should recover gracefully, not crash.
    await engine.send_message("Try again.")
    await asyncio.sleep(0.1)
    # The mock LLM returns a fixed text, so the loop should COMPLETE.
    assert (await engine.get_snapshot())["state"] == "COMPLETED"



# ──────────────────────────────────────────────────────────────────────
# Pending command queue (RUNNING 期间新命令排队)
# ──────────────────────────────────────────────────────────────────────

class _BlockingLLM:
    """Stays inside chat until released — used to force RUNNING state."""
    def __init__(self) -> None:
        self._released = asyncio.Event()

    async def chat(self, messages, tools=None):
        await self._released.wait()
        return Message(role="assistant", content=[TextBlock(text="Done.")])

    async def stream_chat(self, messages, tools=None, on_token=None):
        return await self.chat(messages, tools)

    async def complete(self, prompt):
        return ""

    def release(self) -> None:
        self._released.set()


def _build_blocking_engine(llm):
    session_id = "test-pending-queue"
    emitter = EventEmitter(session_id)
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


@pytest.mark.asyncio
async def test_send_message_returns_started_when_idle():
    """First send_message on an idle engine returns status='started'."""
    engine = _build_engine("Reply.")
    result = await engine.send_message("Hello")
    assert result["status"] == "started"
    assert result["queue_size"] == 0
    assert result["queue"] == []


@pytest.mark.asyncio
async def test_send_message_returns_queued_when_running():
    """While the engine is RUNNING, send_message returns status='queued'."""
    llm = _BlockingLLM()
    engine = _build_blocking_engine(llm)
    first = await engine.send_message("first")
    assert first["status"] == "started"
    await asyncio.sleep(0.05)
    assert engine._sm.state == EngineState.RUNNING
    second = await engine.send_message("second")
    assert second["status"] == "queued"
    assert second["index"] == 2
    assert second["text"] == "second"
    assert "submitted_at" in second
    assert second["queue_size"] == 1
    assert second["queue"][0]["index"] == 2
    assert second["queue"][0]["text"] == "second"
    llm.release()
    await asyncio.sleep(0.1)


@pytest.mark.asyncio
async def test_queue_duplicate_text_keeps_distinct_indexes():
    """Three identical texts in a row must each get a unique index."""
    llm = _BlockingLLM()
    engine = _build_blocking_engine(llm)
    await engine.send_message("1")
    await asyncio.sleep(0.05)
    assert engine._sm.state == EngineState.RUNNING
    r2 = await engine.send_message("1")
    r3 = await engine.send_message("1")
    assert r2["status"] == "queued" and r2["index"] == 2
    assert r3["status"] == "queued" and r3["index"] == 3
    pending = await engine.get_pending_commands()
    assert len(pending) == 2
    assert pending[0]["index"] == 2 and pending[0]["text"] == "1"
    assert pending[1]["index"] == 3 and pending[1]["text"] == "1"
    llm.release()
    await asyncio.sleep(0.1)


@pytest.mark.asyncio
async def test_cancel_pending_command_by_index():
    """Cancelling one queued entry by index removes only that entry."""
    llm = _BlockingLLM()
    engine = _build_blocking_engine(llm)
    await engine.send_message("live")
    await asyncio.sleep(0.05)
    assert engine._sm.state == EngineState.RUNNING
    await engine.send_message("a")
    await engine.send_message("b")
    await engine.send_message("c")
    pending = await engine.get_pending_commands()
    assert [p["index"] for p in pending] == [2, 3, 4]
    result = await engine.cancel_pending_command(3)
    assert result["cancelled"] is True
    assert result["index"] == 3
    assert result["queue_size"] == 2
    after = await engine.get_pending_commands()
    assert [p["index"] for p in after] == [2, 4]
    assert after[0]["text"] == "a"
    assert after[1]["text"] == "c"
    miss = await engine.cancel_pending_command(999)
    assert miss["cancelled"] is False
    llm.release()
    await asyncio.sleep(0.1)


@pytest.mark.asyncio
async def test_cancel_pending_does_not_remove_live_message():
    """Cancelling a pending command must NOT remove the live user message."""
    llm = _BlockingLLM()
    engine = _build_blocking_engine(llm)
    await engine.send_message("live")
    await asyncio.sleep(0.05)
    await engine.send_message("queued-only")
    snap_before = await engine.get_snapshot()
    n_before = sum(1 for m in snap_before["last_messages"] if m["role"] == "user")
    assert n_before == 1
    await engine.cancel_pending_command(2)
    snap_after = await engine.get_snapshot()
    n_after = sum(1 for m in snap_after["last_messages"] if m["role"] == "user")
    assert n_after == 1
    llm.release()
    await asyncio.sleep(0.1)
