from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

from harness.types.messages import Message
from harness.types.tools import ToolSchema

TokenCallback = Callable[[str], Awaitable[None]]


@dataclass
class LLMConfig:
    model: str
    api_key: str
    base_url: str = ""
    timeout: float = 60.0
    max_tokens: int = 4096
    temperature: float = 0.0
    # Provider-specific extras: thinking config, etc.
    extra: dict[str, Any] = field(default_factory=dict)


class LLMProvider(ABC):
    def __init__(self, config: LLMConfig) -> None:
        self.config = config

    @abstractmethod
    async def chat(
        self,
        messages: list[Message],
        tools: list[ToolSchema] | None = None,
    ) -> Message:
        """Send messages to LLM. Return assistant Message (may contain ToolCallBlocks)."""

    @abstractmethod
    async def complete(self, prompt: str) -> str:
        """Single-turn completion — used by the context compressor."""

    async def stream_chat(
        self,
        messages: list[Message],
        tools: list[ToolSchema] | None = None,
        on_token: TokenCallback | None = None,
    ) -> Message:
        """Streaming chat. Providers that support it override this.
        Default: falls back to chat() (no token-by-token delivery)."""
        return await self.chat(messages, tools)

    def _thinking_params(self) -> dict[str, Any]:
        """Extract thinking config from extra. Used by concrete implementations."""
        return self.config.extra.get("thinking", {})
