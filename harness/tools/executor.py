from __future__ import annotations
import asyncio
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
        # 允许调用方传入自定义 limits（来自 config.yaml tools.limits）
        self._limits: dict[str, int] = limits if limits is not None else dict(LIMITS)

    async def execute_all(
        self, calls: list[ToolCallBlock], round_idx: int
    ) -> list[ToolResultBlock]:
        """
        Execute all tool calls concurrently (independent within a round).
        Returns results in the SAME ORDER as calls.
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
            raw_output: str = await tool.handler(**call.tool_input)
        except Exception as exc:
            self._emitter.emit(
                "tool_call", "execution-error",
                detail={"tool": call.tool_name, "error": str(exc), "round": round_idx},
            )
            return ToolResultBlock(
                tool_call_id=call.tool_call_id,
                content=f"Error executing '{call.tool_name}': {exc}",
                is_error=True,
                tool_name=call.tool_name,
            )

        limit = self._limits.get(call.tool_name, DEFAULT_LIMIT)
        if len(raw_output) > limit:
            ref_id = await self._overflow.store(raw_output)
            self._emitter.emit(
                "tool_output_overflow", "triggered-intercepted",
                detail={
                    "tool": call.tool_name,
                    "ref_id": ref_id,
                    "original_len": len(raw_output),
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
            content=raw_output,
            tool_name=call.tool_name,
        )
