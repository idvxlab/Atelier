"""
ToolExecutor — runs tool calls concurrently and wraps their output.

Supports a single interrupt channel: a tool may return a result whose
`is_interrupt` flag is True. The executor still wraps it in a ToolResultBlock
so the assistant→tool pair satisfies the protocol, but the run loop reads
`is_interrupt` and pauses the agent run at the engine level.
"""
from __future__ import annotations
import asyncio
import inspect
import traceback
from typing import Any, Callable, Awaitable
from harness.types.messages import ToolCallBlock, ToolResultBlock
from harness.tools.registry import ToolRegistry
from harness.tools.overflow import OverflowStore
from harness.observability.events import EventEmitter

# Hard output limits in characters
LIMITS: dict[str, int] = {
    "read_file": 20_000,
    "search":    10_000,
    "shell":     15_000,
}
DEFAULT_LIMIT = 8_000


def _accepts_tool_call_id(handler: Callable[..., Any]) -> bool:
    """
    True iff the handler signature accepts a `_tool_call_id` keyword argument.

    The executor uses this to decide whether to inject the LLM-generated
    tool_call_id (used by interruptible tools like ask_user to anchor the
    later rewrite). Existing tools that don't declare this kwarg keep their
    original contract — no breaking change.
    """
    try:
        sig = inspect.signature(handler)
    except (TypeError, ValueError):
        return False
    for name, param in sig.parameters.items():
        if name == "_tool_call_id":
            # Accept any flavour (positional, keyword, positional-or-keyword)
            if param.kind in (
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.KEYWORD_ONLY,
            ):
                return True
    return False


class ToolExecutor:
    def __init__(
        self,
        registry: ToolRegistry,
        overflow: OverflowStore,
        emitter: EventEmitter,
        limits: dict[str, int] | None = None,
    ) -> None:
        self._registry = registry
        self._overflow = overflow
        self._emitter = emitter
        # Allow config-driven limits to override defaults
        self._limits: dict[str, int] = limits if limits is not None else dict(LIMITS)

    async def execute_all(
        self, calls: list[ToolCallBlock], round_idx: int
    ) -> list[ToolResultBlock]:
        """
        Execute all tool calls concurrently (independent within a round).
        Returns results in the SAME ORDER as calls.

        Each result is a non-blocking ToolResultBlock. Tools that need to
        interrupt the run (e.g. ask_user) return a result whose
        `is_interrupt=True`; the executor copies that flag through.
        """
        tasks = [self._execute_one(call, round_idx) for call in calls]
        return list(await asyncio.gather(*tasks))

    async def _execute_one(
        self, call: ToolCallBlock, round_idx: int
    ) -> ToolResultBlock:
        tool = self._registry.get(call.tool_name)

        if tool is None:
            self._emitter.emit(
                "tool_call", "execution-error",
                detail={"tool": call.tool_name, "reason": "not_found", "round": round_idx},
            )
            return ToolResultBlock(
                tool_call_id=call.tool_call_id,
                content=f"Error: tool '{call.tool_name}' not found",
                is_error=True,
                tool_name=call.tool_name,
            )

        try:
            self._emitter.emit(
                "tool_call", "triggered-executed",
                detail={"tool": call.tool_name, "round": round_idx},
            )
            # The executor threads the LLM-generated tool_call_id to the
            # handler as a reserved kwarg _tool_call_id, but ONLY if the
            # handler signature accepts it. This keeps backwards-compat
            # for existing tools and lets interruptible tools (ask_user)
            # anchor the placeholder rewrite.
            if _accepts_tool_call_id(tool.handler):
                raw_output: Any = await tool.handler(
                    _tool_call_id=call.tool_call_id, **call.tool_input,
                )
            else:
                raw_output: Any = await tool.handler(**call.tool_input)
        except Exception as exc:
            detail = str(exc).strip() or repr(exc)
            if detail == repr(exc):
                detail = f"{type(exc).__name__}: {detail}"
            tb_last = traceback.format_exc().strip().splitlines()[-1]
            self._emitter.emit(
                "tool_call", "execution-error",
                detail={"tool": call.tool_name, "error": detail, "round": round_idx},
            )
            return ToolResultBlock(
                tool_call_id=call.tool_call_id,
                content=f"Error executing '{call.tool_name}': {detail}\n{tb_last}",
                is_error=True,
                tool_name=call.tool_name,
            )

        # Tool handlers may return either a plain string (the historical
        # contract) OR an InterruptibleToolResult object that carries an
        # is_interrupt flag. We detect the latter by duck-typing.
        is_interrupt = False
        if hasattr(raw_output, "is_interrupt") and hasattr(raw_output, "content"):
            content = str(raw_output.content)
            is_interrupt = bool(raw_output.is_interrupt)
        else:
            content = str(raw_output) if raw_output is not None else ""

        # Overflow handling only for non-interrupt results (interrupt placeholders
        # are tiny handles, never truncated).
        if is_interrupt:
            return ToolResultBlock(
                tool_call_id=call.tool_call_id,
                content=content,
                is_interrupt=True,
                tool_name=call.tool_name,
            )

        limit = self._limits.get(call.tool_name, DEFAULT_LIMIT)
        if len(content) > limit:
            ref_id = await self._overflow.store(content)
            self._emitter.emit(
                "tool_output_overflow", "triggered-intercepted",
                detail={
                    "tool": call.tool_name,
                    "ref_id": ref_id,
                    "original_len": len(content),
                    "limit": limit,
                    "round": round_idx,
                },
            )
            return ToolResultBlock(
                tool_call_id=call.tool_call_id,
                content=f"[Output exceeded {limit} char limit. Full output stored at ref:{ref_id}]",
                is_overflow_ref=True,
                tool_name=call.tool_name,
            )

        return ToolResultBlock(
            tool_call_id=call.tool_call_id,
            content=content,
            tool_name=call.tool_name,
        )


class InterruptibleToolResult:
    """
    Returned by interruptible tool handlers (e.g. ask_user) to signal that
    the run loop should pause at the engine level after the tool batch.

    The tool returns this object IMMEDIATELY (no blocking). The executor
    copies the `is_interrupt` flag into the ToolResultBlock, and the
    engine's run loop checks that flag to decide whether to pause.
    """

    def __init__(self, content: str):
        self.content = content
        self.is_interrupt: bool = True
