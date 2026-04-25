"""Tests for two-layer context compression."""
from __future__ import annotations

import pytest

from harness.engine.compression import CompressionConfig, ContextCompressor, _estimate_tokens
from harness.types.messages import Message, TextBlock, ToolCallBlock, ToolResultBlock


class _MockSummarizer:
    async def complete(self, prompt: str) -> str:
        return "SUMMARY"


def _make_tool_round(round_idx: int) -> tuple[Message, Message]:
    """Build a valid (assistant tool_call, tool_result) message pair."""
    call_id = f"call-{round_idx}"
    assistant = Message(
        role="assistant",
        content=[ToolCallBlock(tool_call_id=call_id, tool_name="shell", tool_input={})],
        round_index=round_idx,
    )
    tool = Message(
        role="tool",
        content=[ToolResultBlock(tool_call_id=call_id, content=f"output-{round_idx}")],
        round_index=round_idx,
    )
    return assistant, tool


def _make_user_msg(text: str, round_idx: int = 0) -> Message:
    return Message(role="user", content=[TextBlock(text=text)], round_index=round_idx)


# ──────────────────────────────────────────────────────────────────────
# Micro compression
# ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_micro_compression_clears_old_tool_results():
    """Old tool result content should be replaced with a placeholder."""
    cfg = CompressionConfig(
        token_window=1_000_000,  # won't trigger auto
        micro_keep_recent=2,
    )
    compressor = ContextCompressor(summarizer=_MockSummarizer(), config=cfg)

    messages: list[Message] = []
    # 6 rounds of tool calls → 12 messages + 1 user = 13 messages
    messages.append(_make_user_msg("Start"))
    for i in range(6):
        a, t = _make_tool_round(i)
        messages.extend([a, t])

    result = await compressor.maybe_compress(messages, round_idx=6)

    # Old tool results should be cleared
    old_tool_msgs = [m for m in result if m.role == "tool" and m.round_index < 4]
    for msg in old_tool_msgs:
        for block in msg.content:
            if isinstance(block, ToolResultBlock):
                assert block.content == "[cleared by micro-compression]"

    # Recent rounds should be intact
    recent_tool_msgs = [m for m in result if m.role == "tool" and m.round_index >= 4]
    for msg in recent_tool_msgs:
        for block in msg.content:
            if isinstance(block, ToolResultBlock):
                assert block.content != "[cleared by micro-compression]"


@pytest.mark.asyncio
async def test_micro_does_not_break_protocol():
    """After micro-compression, tool_call IDs must still match tool_result IDs."""
    from harness.types.messages import validate_message_sequence

    cfg = CompressionConfig(token_window=1_000_000, micro_keep_recent=1)
    compressor = ContextCompressor(summarizer=_MockSummarizer(), config=cfg)

    messages: list[Message] = [_make_user_msg("Start")]
    for i in range(5):
        a, t = _make_tool_round(i)
        messages.extend([a, t])

    result = await compressor.maybe_compress(messages, round_idx=5)
    # Should not raise
    validate_message_sequence(result)


# ──────────────────────────────────────────────────────────────────────
# Auto compression
# ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_auto_compression_triggered_at_ratio():
    """Auto compression fires when token estimate / window >= ratio."""
    # Make a tiny window so it's easy to exceed
    cfg = CompressionConfig(
        token_window=100,
        auto_trigger_ratio=0.5,
        micro_keep_recent=1,
        task_goal="Write a report",
        system_identity="You are a helpful agent",
    )
    compressor = ContextCompressor(summarizer=_MockSummarizer(), config=cfg)

    # Build messages that collectively exceed 50 tokens (~200 chars)
    messages = [
        _make_user_msg("A" * 300, round_idx=0),
    ]
    for i in range(3):
        a, t = _make_tool_round(i)
        messages.extend([a, t])

    result = await compressor.maybe_compress(messages, round_idx=3)

    # Should contain the summary message
    texts = [b.text for m in result for b in m.content if isinstance(b, TextBlock)]
    assert any("SUMMARY" in t for t in texts)


@pytest.mark.asyncio
async def test_auto_compression_reinjects_identity_and_goal():
    """After auto-compression, system identity and task goal MUST be present."""
    cfg = CompressionConfig(
        token_window=10,
        auto_trigger_ratio=0.1,
        micro_keep_recent=1,
        task_goal="My important goal",
        system_identity="You are Agent X",
    )
    compressor = ContextCompressor(summarizer=_MockSummarizer(), config=cfg)

    messages = [_make_user_msg("Start" * 20, round_idx=0)]
    result = await compressor.maybe_compress(messages, round_idx=0)

    system_msgs = [m for m in result if m.role == "system"]
    assert system_msgs, "System identity not re-injected"
    identity_text = system_msgs[0].content[0].text
    assert "Agent X" in identity_text

    goal_texts = [
        b.text for m in result for b in m.content
        if isinstance(b, TextBlock) and "goal" in b.text.lower()
    ]
    assert any("My important goal" in t for t in goal_texts)


# ──────────────────────────────────────────────────────────────────────
# Token estimator
# ──────────────────────────────────────────────────────────────────────

def test_estimate_tokens_basic():
    msgs = [Message(role="user", content=[TextBlock(text="A" * 400)])]
    tokens = _estimate_tokens(msgs)
    assert tokens == 100  # 400 chars // 4
