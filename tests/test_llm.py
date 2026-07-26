"""Tests for the message protocol and LLM type conversions."""
from __future__ import annotations

import pytest

from harness.types.messages import (
    Message,
    TextBlock,
    ThinkingBlock,
    ToolCallBlock,
    ToolResultBlock,
    ProtocolViolationError,
    repair_message_sequence,
    validate_message_sequence,
)
from harness.types.tools import ToolSchema, ToolParam
from harness.llm.base import LLMConfig
from harness.llm.openai_provider import OpenAIProvider, _parse_tool_arguments


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

    def test_repair_message_sequence_adds_missing_tool_result(self):
        msgs = [
            _user("go"),
            _assistant_tool("missing-result", "shell"),
            _assistant_text("continued too early"),
        ]

        repaired = repair_message_sequence(msgs)

        validate_message_sequence(repaired)
        assert repaired[2].role == "tool"
        result = repaired[2].content[0]
        assert isinstance(result, ToolResultBlock)
        assert result.tool_call_id == "missing-result"
        assert result.is_error

    def test_repair_message_sequence_handles_system_after_tool_call(self):
        msgs = [
            _user("go"),
            _assistant_tool("missing-result", "todo_write"),
            Message(role="system", content=[TextBlock(text="<internal>reminder</internal>")]),
        ]

        repaired = repair_message_sequence(msgs)

        validate_message_sequence(repaired)
        assert repaired[2].role == "tool"
        assert repaired[3].role == "system"


def test_openai_tool_arguments_parse_truncated_json_as_invalid():
    parsed = _parse_tool_arguments('{"path": "demo.py", "content": "unterminated')

    assert parsed["_invalid_tool_arguments"] is True
    assert "Unterminated string" in parsed["_error"]
    assert parsed["_raw"].startswith('{"path"')


def test_openai_tool_arguments_must_be_object():
    parsed = _parse_tool_arguments('["not", "an", "object"]')

    assert parsed["_invalid_tool_arguments"] is True
    assert "JSON object" in parsed["_error"]


def test_openai_response_reasoning_content_becomes_thinking_block():
    class _Message:
        role = "assistant"
        content = "final answer"
        tool_calls = None
        model_extra = {"reasoning_content": "hidden reasoning summary"}

    class _Choice:
        message = _Message()

    class _Response:
        choices = [_Choice()]

    provider = OpenAIProvider(LLMConfig(model="test", api_key="sk-test"))
    msg = provider._from_openai_response(_Response())

    assert isinstance(msg.content[0], ThinkingBlock)
    assert msg.content[0].thinking == "hidden reasoning summary"
    assert isinstance(msg.content[1], TextBlock)
    assert msg.content[1].text == "final answer"


def test_openai_messages_preserve_thinking_as_reasoning_content():
    provider = OpenAIProvider(LLMConfig(model="test", api_key="sk-test"))

    converted = provider._to_openai_messages(
        [
            Message(
                role="assistant",
                content=[
                    ThinkingBlock(thinking="visible reasoning"),
                    TextBlock(text="final answer"),
                ],
            )
        ]
    )

    assert converted == [
        {
            "role": "assistant",
            "content": "final answer",
            "reasoning_content": "visible reasoning",
        }
    ]


@pytest.mark.asyncio
async def test_openai_stream_reasoning_content_emits_thinking_tokens():
    class _Delta:
        def __init__(self, content=None, reasoning=None):
            self.content = content
            self.tool_calls = None
            self.model_extra = {}
            if reasoning is not None:
                self.model_extra["reasoning_content"] = reasoning

    class _Choice:
        def __init__(self, delta):
            self.delta = delta

    class _Chunk:
        def __init__(self, delta):
            self.choices = [_Choice(delta)]

    class _Stream:
        def __aiter__(self):
            self._items = iter([
                _Chunk(_Delta(reasoning="think-a")),
                _Chunk(_Delta(reasoning="think-b")),
                _Chunk(_Delta(content="answer")),
            ])
            return self

        async def __anext__(self):
            try:
                return next(self._items)
            except StopIteration:
                raise StopAsyncIteration

    class _Completions:
        async def create(self, **kwargs):
            return _Stream()

    class _Chat:
        completions = _Completions()

    class _Client:
        chat = _Chat()

    provider = OpenAIProvider(LLMConfig(model="test", api_key="sk-test"))
    provider._client = _Client()
    tokens: list[str] = []

    async def collect_token(text: str) -> None:
        tokens.append(text)

    msg = await provider.stream_chat(
        [Message(role="user", content=[TextBlock(text="hi")])],
        on_token=collect_token,
    )

    assert tokens == [
        "\x00THINKING\x00",
        "\x00THINKING_TOKEN\x00think-a",
        "\x00THINKING_TOKEN\x00think-b",
        "answer",
    ]
    assert isinstance(msg.content[0], ThinkingBlock)
    assert msg.content[0].thinking == "think-athink-b"
    assert isinstance(msg.content[1], TextBlock)
    assert msg.content[1].text == "answer"


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
