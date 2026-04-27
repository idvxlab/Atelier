"""Tests for streaming pipeline: stream_chat -> token listeners -> message listeners."""
from __future__ import annotations

import asyncio
import pytest

from harness.engine.engine import AgentEngine, EngineConfig
from harness.engine.loop import ReactLoop
from harness.engine.compression import CompressionConfig, ContextCompressor
from harness.observability.events import EventEmitter
from harness.tools.executor import ToolExecutor
from harness.tools.registry import ToolRegistry
from harness.tools.overflow import OverflowStore
from harness.storage.backends.memory import MemorySessionStore
from harness.types.messages import Message, TextBlock, ToolCallBlock, ToolResultBlock


# ──────────────────────────────────────────────────────────────────────
# Shared mock LLM
# ──────────────────────────────────────────────────────────────────────

TOKENS = ["Hello", ", ", "world", "!"]


class _StreamingLLM:
    """Calls on_token for each token in TOKENS, then returns the full message."""

    async def chat(self, messages, tools=None):
        return Message(role="assistant", content=[TextBlock(text="".join(TOKENS))])

    async def stream_chat(self, messages, tools=None, on_token=None):
        if on_token:
            for tok in TOKENS:
                await on_token(tok)
        return await self.chat(messages, tools)

    async def complete(self, prompt: str) -> str:
        return "Summary."


def _build_engine(llm=None) -> AgentEngine:
    sid = "stream-test"
    emitter = EventEmitter(sid)
    if llm is None:
        llm = _StreamingLLM()
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
        config=EngineConfig(session_id=sid),
        loop=loop,
        session_store=MemorySessionStore(),
        emitter=emitter,
    )


# ──────────────────────────────────────────────────────────────────────
# Token listener tests
# ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_token_listener_receives_tokens():
    """Token listener should get each streamed chunk before the message completes."""
    engine = _build_engine()

    received: list[str] = []

    async def on_token(text: str) -> None:
        received.append(text)

    engine.add_token_listener(on_token)
    await engine.send_message("Say hello.")
    await asyncio.sleep(0.15)

    assert received == TOKENS, f"Expected {TOKENS}, got {received}"


@pytest.mark.asyncio
async def test_token_listener_fires_before_message_listener():
    """Tokens arrive before the final full-message callback."""
    engine = _build_engine()

    events: list[str] = []

    async def on_token(text: str) -> None:
        events.append(f"token:{text}")

    async def on_message(msg: Message) -> None:
        events.append(f"message:{msg.role}")

    engine.add_token_listener(on_token)
    engine.add_message_listener(on_message)
    await engine.send_message("Hello.")
    await asyncio.sleep(0.15)

    # All tokens should appear before the "message:assistant" event
    assert "message:assistant" in events
    first_msg_idx = events.index("message:assistant")
    token_events = [e for e in events[:first_msg_idx] if e.startswith("token:")]
    assert len(token_events) == len(TOKENS)


@pytest.mark.asyncio
async def test_remove_token_listener_stops_delivery():
    """Removing a listener before run means it gets no tokens."""
    engine = _build_engine()

    received: list[str] = []

    async def on_token(text: str) -> None:
        received.append(text)

    engine.add_token_listener(on_token)
    engine.remove_token_listener(on_token)

    await engine.send_message("Hello.")
    await asyncio.sleep(0.15)

    assert received == []


@pytest.mark.asyncio
async def test_broken_token_listener_does_not_crash_engine():
    """A listener that raises must not crash the agent loop."""
    engine = _build_engine()

    async def bad_listener(text: str) -> None:
        raise RuntimeError("simulated listener crash")

    engine.add_token_listener(bad_listener)
    await engine.send_message("Hello.")
    await asyncio.sleep(0.15)

    snapshot = await engine.get_snapshot()
    assert snapshot["state"] == "COMPLETED"


# ──────────────────────────────────────────────────────────────────────
# stream_chat + tool call correctness
# ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_streaming_with_tool_call_protocol():
    """Tool-call protocol stays valid even when streaming is active."""

    class _ToolLLM:
        """Round 0: returns a tool call.  Round 1: returns text (done)."""
        def __init__(self):
            self.round = 0

        async def chat(self, messages, tools=None):
            if self.round == 0:
                self.round += 1
                return Message(
                    role="assistant",
                    content=[ToolCallBlock(tool_call_id="t1", tool_name="noop", tool_input={})],
                )
            return Message(role="assistant", content=[TextBlock(text="Finished.")])

        async def stream_chat(self, messages, tools=None, on_token=None):
            return await self.chat(messages, tools)

        async def complete(self, prompt):
            return "Summary."

    from harness.types.tools import ToolSchema, ToolParam

    llm = _ToolLLM()
    engine = _build_engine(llm)

    # Register a "noop" tool so executor doesn't fail
    from harness.tools.registry import ToolRegistry
    noop_schema = ToolSchema(
        name="noop",
        description="Does nothing.",
        params=[],
    )

    async def noop_handler(**_kwargs):
        return "ok"

    engine._loop._registry.register(noop_schema, noop_handler)

    tokens: list[str] = []

    async def collect_token(text: str) -> None:
        tokens.append(text)

    engine.add_token_listener(collect_token)
    await engine.send_message("Do the thing.")
    await asyncio.sleep(0.2)

    snapshot = await engine.get_snapshot()
    assert snapshot["state"] == "COMPLETED"
    # Last assistant message should be "Finished."
    assistant_msgs = [m for m in snapshot["last_messages"] if m["role"] == "assistant"]
    last_text = "".join(
        b["text"] for b in assistant_msgs[-1]["content"] if b.get("type") == "text"
    )
    assert "Finished." in last_text
