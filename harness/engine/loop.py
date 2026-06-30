"""
ReAct loop — the core agent cycle.

Per-round sequence (enforced strictly):
  1. Check cancel signal → raise CancelledError immediately if set
  2. Run context compression (before LLM call)
  3. Reload tool list from registry (never cached)
  4. Call LLM
  5. If no tool_calls → drain intervention queue → return (done)
  6. Check LoopDetector → if repeated, inject break message, continue
  7. Execute all tools concurrently via asyncio.gather
  8. Validate the (assistant, tool_result) pair with validate_message_sequence
  9. Append the pair atomically via on_message callbacks
 10. If any tool_result has is_interrupt=True → raise InterruptSignal
     (engine catches it and pauses the run at the engine level)
 11. Drain intervention queue ONLY after tool_result is flushed
"""
from __future__ import annotations

import asyncio
from typing import Callable, Awaitable

from harness.types.messages import (
    Message,
    TextBlock,
    ToolResultBlock,
    validate_message_sequence,
)
from harness.engine.compression import ContextCompressor
from harness.engine.loop_detector import LoopDetector
from harness.engine.prompt_cache import PromptCache
from harness.llm.base import LLMProvider, TokenCallback
from harness.tools.registry import ToolRegistry
from harness.tools.executor import ToolExecutor
from harness.observability.events import EventEmitter

OnMessageCallback = Callable[[Message], Awaitable[None]]


class InterruptSignal(BaseException):
    """
    Raised by the loop when a tool result is interruptible (is_interrupt=True).

    The loop is NOT the right place to wait for the user. The engine
    (AgentEngine._run_loop_guarded) catches this signal, transitions the
    state machine to WAITING_INPUT, and returns. External code is then
    responsible for calling engine.resume_question() when the user replies.

    BaseException (not Exception) so the signal can't be swallowed by
    a generic `except Exception` in tool code.
    """
    def __init__(self, request_id: str, tool_call_id: str, round_idx: int):
        self.request_id = request_id
        self.tool_call_id = tool_call_id
        self.round_idx = round_idx
        super().__init__(
            f"interrupt request_id={request_id} tool_call_id={tool_call_id}"
        )


class ReactLoop:
    def __init__(
        self,
        llm: LLMProvider,
        tool_registry: ToolRegistry,
        tool_executor: ToolExecutor,
        compressor: ContextCompressor,
        emitter: EventEmitter,
        max_rounds: int = 50,
        prompt_cache: PromptCache | None = None,
    ) -> None:
        self._llm = llm
        self._registry = tool_registry
        self._executor = tool_executor
        self._compressor = compressor
        self._emitter = emitter
        self._max_rounds = max_rounds
        self._detector = LoopDetector(window=5, threshold=2)
        self._prompt_cache: PromptCache = prompt_cache if prompt_cache is not None else PromptCache()

    async def run(
        self,
        messages: list[Message],
        cancel_event: asyncio.Event,
        intervention_queue: asyncio.Queue[Message],
        on_message: OnMessageCallback,
        on_token: TokenCallback | None = None,
        on_pre_execute: Callable[[list], Awaitable[bool]] | None = None,
        drain_callback: Callable[[str], Awaitable[None]] | None = None,
    ) -> None:
        """
        Main ReAct cycle. `messages` is the live list owned by AgentEngine.
        This method appends to it exclusively via `on_message` so the engine
        can update its state atomically.

        `drain_callback(text)` is called with each queued user message text
        when it is drained from the intervention queue. Used by AgentEngine
        to remove the corresponding entry from _pending_commands.
        """
        for round_idx in range(self._max_rounds):
            self._emitter.set_round(round_idx)

            # ── 1. Cancel check at round START (must be immediate) ─────────
            if cancel_event.is_set():
                self._emitter.emit(
                    "cancel_check", "triggered-executed",
                    detail={"round": round_idx},
                )
                raise asyncio.CancelledError("cancel signal received at round start")
            else:
                self._emitter.emit(
                    "cancel_check", "condition-not-met",
                    detail={"round": round_idx},
                )

            # ── 2. Context compression ─────────────────────────────────────
            compressed = await self._compressor.maybe_compress(messages, round_idx)
            if compressed is not messages:
                # Replace contents in-place so the engine's reference stays valid
                messages[:] = compressed
                self._emitter.emit(
                    "compression_applied", "triggered-executed",
                    detail={"round": round_idx, "msg_count": len(messages)},
                )

            # ── 3. Load tool schemas (from cache or fresh) ────────────────
            # We cache the ToolSchema objects themselves (they are immutable after
            # registry is built). Storing the objects rather than dicts means the
            # LLM provider's _to_openai_tool() call works without changes.
            # The cache is refreshed only when `refresh_tool_schemas()` is called
            # (rare — only if the tool registry changes at runtime).
            cached_schemas = self._prompt_cache.get_tool_schemas()
            if cached_schemas is not None:
                tools = cached_schemas
            else:
                fresh = [t.schema for t in self._registry.discover()]
                self._prompt_cache.set_tool_schemas(fresh)
                tools = fresh

            # ── 4. LLM call (races against cancel_event) ───────────────────
            self._emitter.emit(
                "llm_call", "triggered-executed",
                detail={"round": round_idx, "msg_count": len(messages)},
            )
            reply: Message = await self._chat_or_cancel(messages, tools, cancel_event, on_token)
            reply.round_index = round_idx

            # ── 5. No tool calls → done ────────────────────────────────────
            if not reply.has_tool_calls():
                await on_message(reply)
                await self._drain_interventions(
                    intervention_queue, round_idx, on_message, drain_callback
                )
                return

            # ── 6. Loop detection ──────────────────────────────────────────
            tool_calls = reply.tool_calls()
            if self._detector.is_repeated(tool_calls):
                self._emitter.emit(
                    "loop_detected", "triggered-intercepted",
                    detail={
                        "round": round_idx,
                        "tools": [c.tool_name for c in tool_calls],
                    },
                )
                # Inject the assistant reply so the conversation is coherent
                await on_message(reply)
                # Then inject a synthetic break message (user role is safe here
                # because no tool_result is pending at this point — we're
                # short-circuiting before executing tools)
                break_msg = Message(
                    role="user",
                    content=[
                        TextBlock(
                            text=(
                                "[SYSTEM: Repeated tool call detected. "
                                "You are calling the same tools with the same "
                                "arguments repeatedly. Please reconsider your "
                                "approach and try a different strategy.]"
                            )
                        )
                    ],
                    round_index=round_idx,
                )
                await on_message(break_msg)
                continue

            # ── 6.5. Confirmation gate (dangerous tools pause here) ────────
            if on_pre_execute is not None:
                # Raises asyncio.CancelledError if user denies; returns True if approved
                await on_pre_execute(tool_calls)

            # ── 7. Execute all tools concurrently ──────────────────────────
            results: list[ToolResultBlock] = await self._executor.execute_all(
                tool_calls, round_idx
            )

            tool_result_msg = Message(
                role="tool",
                content=results,
                round_index=round_idx,
            )

            # ── 8. Validate the pair BEFORE appending ─────────────────────
            validate_message_sequence(messages + [reply, tool_result_msg])

            # ── 9. Append pair atomically ──────────────────────────────────
            await on_message(reply)
            await on_message(tool_result_msg)

            # ── 9.5. Interrupt detection — engine-level pause ─────────────
            # If any tool result carries is_interrupt=True, the engine
            # owns the waiting state. The loop has finished its job for
            # this round; raise to let the engine pause cleanly.
            interrupt_result = next(
                (r for r in results if getattr(r, "is_interrupt", False)),
                None,
            )
            if interrupt_result is not None:
                # The interrupt request_id is encoded in the placeholder
                # content as a machine-readable line; the engine parses it.
                # We don't import the question type here to keep the loop
                # layer free of domain knowledge — the engine will look up
                # the active QuestionRequest by tool_call_id.
                self._emitter.emit(
                    "tool_interrupt", "triggered-executed",
                    detail={
                        "tool": interrupt_result.tool_name,
                        "tool_call_id": interrupt_result.tool_call_id,
                        "round": round_idx,
                    },
                )
                raise InterruptSignal(
                    request_id="",  # engine looks up by tool_call_id
                    tool_call_id=interrupt_result.tool_call_id,
                    round_idx=round_idx,
                )

            # ── 10. Drain interventions ONLY after tool_result is flushed ──
            await self._drain_interventions(
                intervention_queue, round_idx, on_message
            )

        # Exceeded max rounds
        self._emitter.emit(
            "max_rounds_exceeded", "execution-error",
            detail={"max_rounds": self._max_rounds},
        )

    async def _chat_or_cancel(
        self,
        messages: list[Message],
        tools: list,
        cancel_event: asyncio.Event,
        on_token: TokenCallback | None = None,
    ) -> Message:
        """
        Run the LLM call concurrently with a cancel-event watcher.
        Uses stream_chat when on_token is provided; chat otherwise.
        If cancel fires before the LLM responds, abort the LLM task immediately.
        """
        llm_task = asyncio.ensure_future(
            self._llm.stream_chat(messages, tools, on_token)
        )
        cancel_task = asyncio.ensure_future(cancel_event.wait())
        try:
            done, pending = await asyncio.wait(
                [llm_task, cancel_task], return_when=asyncio.FIRST_COMPLETED
            )
        finally:
            cancel_task.cancel()

        if cancel_event.is_set():
            llm_task.cancel()
            try:
                await llm_task
            except (asyncio.CancelledError, Exception):
                pass
            self._emitter.emit(
                "cancel_check", "triggered-executed",
                detail={"phase": "during_llm_call"},
            )
            raise asyncio.CancelledError("cancel signal received during LLM call")

        return llm_task.result()

    async def _drain_interventions(
        self,
        queue: asyncio.Queue[Message],
        round_idx: int,
        on_message: OnMessageCallback,
        drain_callback: Callable[[str], Awaitable[None]] | None = None,
    ) -> None:
        """Flush queued user intervention messages after a safe point."""
        while not queue.empty():
            msg = queue.get_nowait()
            msg.round_index = round_idx
            await on_message(msg)
            if drain_callback:
                text_blocks = [b.text for b in msg.content if hasattr(b, "text")]
                if text_blocks:
                    await drain_callback(text_blocks[0])
