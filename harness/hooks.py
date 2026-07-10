from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable


@dataclass(frozen=True)
class HookEvent:
    """Structured runtime event passed to internal hooks."""

    name: str
    session_id: str = ""
    round_index: int | None = None
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class HookResult:
    """Result returned by a hook handler."""

    continue_: bool = True
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


HookHandler = Callable[[HookEvent], HookResult | Awaitable[HookResult | None] | None]


class HookManager:
    """
    Minimal internal hook registry.

    Hooks can observe lifecycle events and optionally block a flow. Payload
    mutation is deliberately left out of the first version so the extension
    point stays predictable.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[HookHandler]] = {}

    def register(self, name: str, handler: HookHandler) -> None:
        self._handlers.setdefault(name, []).append(handler)

    def unregister(self, name: str, handler: HookHandler) -> None:
        handlers = self._handlers.get(name)
        if not handlers:
            return
        try:
            handlers.remove(handler)
        except ValueError:
            return
        if not handlers:
            self._handlers.pop(name, None)

    async def emit(self, event: HookEvent) -> HookResult:
        for handler in list(self._handlers.get(event.name, [])):
            result = handler(event)
            if inspect.isawaitable(result):
                result = await result
            if result is None:
                continue
            if not result.continue_:
                return result
        return HookResult()
