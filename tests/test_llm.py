"""Tests for the message protocol and LLM type conversions."""
from __future__ import annotations

import pytest

from harness.types.messages import (
    Message,
    TextBlock,
    ToolCallBlock,
    ToolResultBlock,
    ProtocolViolationError,
    validate_message_sequence,
)
from harness.types.tools import ToolSchema, ToolParam


# ──────────────────────────────────────────────────────────────────────
# Message protocol validation
# ──────────────────────────────────────────────────────────────────────

def _user(text: str) -> Message:
    return Message(role="user", content=[TextBlock(text=text)])

def _assistant_text(text: str) -> Message:
    return Message(role="assistant", content=[TextBlock(text=text)])

def _assistant_tool(call_id: str, name: str) -> Message:
    return Message(
        role="assistant",
        content=[ToolCallBlock(tool_call_id=call_id, tool_name=name, tool_input={})],
    )

def _tool_result(call_id: str, content: str = "ok") -> Message:
    return Message(
        role="tool",
        content=[ToolResultBlock(tool_call_id=call_id, content=content)],
    )


class TestValidateMessageSequence:
    def test_empty_sequence_ok(self):
        validate_message_sequence([])

    def test_simple_text_exchange_ok(self):
        msgs = [_user("hi"), _assistant_text("hello")]
        validate_message_sequence(msgs)

    def test_tool_call_with_result_ok(self):
        msgs = [
            _user("run something"),
            _assistant_tool("c1", "shell"),
            _tool_result("c1"),
        ]
        validate_message_sequence(msgs)

    def test_multiple_rounds_ok(self):
        msgs = [
            _user("go"),
            _assistant_tool("c1", "shell"),
            _tool_result("c1"),
            _assistant_text("Done"),
        ]
        validate_message_sequence(msgs)

    def test_tool_call_at_end_raises(self):
        msgs = [_user("go"), _assistant_tool("c1", "shell")]
        with pytest.raises(ProtocolViolationError, match="last message"):
            validate_message_sequence(msgs)

    def test_tool_call_followed_by_user_raises(self):
        msgs = [
            _user("go"),
            _assistant_tool("c1", "shell"),
            _user("oops"),  # must be tool, not user
        ]
        with pytest.raises(ProtocolViolationError):
            validate_message_sequence(msgs)

    def test_mismatched_ids_raises(self):
        msgs = [
            _user("go"),
            _assistant_tool("c1", "shell"),
            _tool_result("c2"),  # wrong ID
        ]
        with pytest.raises(ProtocolViolationError, match="do not match"):
            validate_message_sequence(msgs)

    def test_tool_msg_without_preceding_assistant_raises(self):
        msgs = [_user("go"), _tool_result("c1")]
        with pytest.raises(ProtocolViolationError):
            validate_message_sequence(msgs)


# ──────────────────────────────────────────────────────────────────────
# Message helpers
# ──────────────────────────────────────────────────────────────────────

class TestMessageHelpers:
    def test_has_tool_calls(self):
        msg = _assistant_tool("c1", "shell")
        assert msg.has_tool_calls()

    def test_no_tool_calls(self):
        msg = _assistant_text("hello")
        assert not msg.has_tool_calls()

    def test_tool_calls_list(self):
        msg = _assistant_tool("c1", "shell")
        calls = msg.tool_calls()
        assert len(calls) == 1
        assert calls[0].tool_name == "shell"

    def test_text_content(self):
        msg = _assistant_text("hello world")
        assert msg.text_content() == "hello world"
