from __future__ import annotations

import json
from typing import Any

import openai

from harness.llm.base import LLMConfig, LLMProvider, TokenCallback
from harness.types.messages import (
    Message,
    TextBlock,
    ToolCallBlock,
    ToolResultBlock,
    ThinkingBlock,
)
from harness.types.tools import ToolSchema


class OpenAIProvider(LLMProvider):
    def __init__(self, config: LLMConfig) -> None:
        super().__init__(config)
        kwargs: dict[str, Any] = {
            "api_key": config.api_key,
            "timeout": config.timeout,
        }
        if config.base_url:
            kwargs["base_url"] = config.base_url
        self._client = openai.AsyncOpenAI(**kwargs)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def chat(
        self,
        messages: list[Message],
        tools: list[ToolSchema] | None = None,
    ) -> Message:
        oai_messages = self._to_openai_messages(messages)
        kwargs: dict[str, Any] = {
            "model": self.config.model,
            "messages": oai_messages,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
        }
        if tools:
            kwargs["tools"] = [self._to_openai_tool(t) for t in tools]
            kwargs["tool_choice"] = "auto"

        response = await self._client.chat.completions.create(**kwargs)
        return self._from_openai_response(response)

    async def complete(self, prompt: str) -> str:
        oai_messages = [{"role": "user", "content": prompt}]
        response = await self._client.chat.completions.create(
            model=self.config.model,
            messages=oai_messages,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
        )
        choice = response.choices[0]
        return choice.message.content or ""

    async def stream_chat(
        self,
        messages: list[Message],
        tools: list[ToolSchema] | None = None,
        on_token: TokenCallback | None = None,
    ) -> Message:
        oai_messages = self._to_openai_messages(messages)
        kwargs: dict[str, Any] = {
            "model": self.config.model,
            "messages": oai_messages,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "stream": True,
        }
        if tools:
            kwargs["tools"] = [self._to_openai_tool(t) for t in tools]
            kwargs["tool_choice"] = "auto"

        text_parts: list[str] = []
        # idx -> {id, name, args}
        tool_calls_raw: dict[int, dict[str, str]] = {}

        response = await self._client.chat.completions.create(**kwargs)
        async for chunk in response:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta.content:
                if on_token is not None:
                    await on_token(delta.content)
                text_parts.append(delta.content)
            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in tool_calls_raw:
                        tool_calls_raw[idx] = {"id": "", "name": "", "args": ""}
                    if tc_delta.id:
                        tool_calls_raw[idx]["id"] += tc_delta.id
                    if tc_delta.function and tc_delta.function.name:
                        tool_calls_raw[idx]["name"] += tc_delta.function.name
                    if tc_delta.function and tc_delta.function.arguments:
                        tool_calls_raw[idx]["args"] += tc_delta.function.arguments

        content: list[Any] = []
        if text_parts:
            content.append(TextBlock(text="".join(text_parts)))
        for idx in sorted(tool_calls_raw):
            raw = tool_calls_raw[idx]
            try:
                tool_input = json.loads(raw["args"])
            except (json.JSONDecodeError, ValueError):
                tool_input = {"_raw": raw["args"]}
            content.append(
                ToolCallBlock(
                    tool_call_id=raw["id"],
                    tool_name=raw["name"],
                    tool_input=tool_input,
                )
            )
        return Message(role="assistant", content=content)

    # ------------------------------------------------------------------
    # Conversion: internal -> OpenAI format
    # ------------------------------------------------------------------

    def _to_openai_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for msg in messages:
            if msg.role == "system":
                text = "\n".join(
                    b.text for b in msg.content if isinstance(b, TextBlock)
                )
                result.append({"role": "system", "content": text})

            elif msg.role == "user":
                text = "\n".join(
                    b.text for b in msg.content if isinstance(b, TextBlock)
                )
                result.append({"role": "user", "content": text})

            elif msg.role == "assistant":
                text_parts = [
                    b.text for b in msg.content if isinstance(b, TextBlock)
                ]
                tool_calls = [
                    b for b in msg.content if isinstance(b, ToolCallBlock)
                ]
                oai_msg: dict[str, Any] = {
                    "role": "assistant",
                    "content": "\n".join(text_parts) if text_parts else None,
                }
                if tool_calls:
                    oai_msg["tool_calls"] = [
                        {
                            "id": tc.tool_call_id,
                            "type": "function",
                            "function": {
                                "name": tc.tool_name,
                                "arguments": json.dumps(tc.tool_input),
                            },
                        }
                        for tc in tool_calls
                    ]
                result.append(oai_msg)

            elif msg.role == "tool":
                # Flatten: one dict per ToolResultBlock
                for block in msg.content:
                    if isinstance(block, ToolResultBlock):
                        result.append(
                            {
                                "role": "tool",
                                "tool_call_id": block.tool_call_id,
                                "content": block.content,
                            }
                        )

        return result

    def _to_openai_tool(self, schema: ToolSchema) -> dict[str, Any]:
        required: list[str] = []
        properties: dict[str, Any] = {}

        for param in schema.params:
            prop: dict[str, Any] = {
                "type": param.type,
                "description": param.description,
            }
            if param.enum:
                prop["enum"] = param.enum
            properties[param.name] = prop
            if param.required:
                required.append(param.name)

        return {
            "type": "function",
            "function": {
                "name": schema.name,
                "description": schema.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }

    # ------------------------------------------------------------------
    # Conversion: OpenAI response -> internal format
    # ------------------------------------------------------------------

    def _from_openai_response(self, response: Any) -> Message:
        choice = response.choices[0]
        oai_msg = choice.message
        content: list[Any] = []

        if oai_msg.content:
            content.append(TextBlock(text=oai_msg.content))

        if oai_msg.tool_calls:
            for tc in oai_msg.tool_calls:
                try:
                    tool_input = json.loads(tc.function.arguments)
                except (json.JSONDecodeError, ValueError):
                    tool_input = {"_raw": tc.function.arguments}
                content.append(
                    ToolCallBlock(
                        tool_call_id=tc.id,
                        tool_name=tc.function.name,
                        tool_input=tool_input,
                    )
                )

        return Message(role="assistant", content=content)
