"""
AgentEngine — single source of truth for one agent session.

Concurrency model:
  All public methods are called from one asyncio event loop.
  _state_lock protects (state, messages) so REST reads always see a
  consistent snapshot.

  Locking rule: take the lock only to read/write state; release it
  BEFORE doing any async work. Long tasks run in a separate Task.

  Three outcome paths from _run_loop_guarded — all restore engine state:
    success   → COMPLETED
    cancelled → WAITING_INPUT   (cancel is expected, not an error)
    exception → ERROR
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

from harness.llm.base import TokenCallback

MessageListener = Callable[["Message"], Awaitable[None]]
StateListener = Callable[[], Awaitable[None]]

from harness.types.messages import Message, TextBlock
from harness.engine.state_machine import StateMachine, EngineState
from harness.engine.loop import ReactLoop
from harness.storage.session import SessionStore
from harness.observability.events import EventEmitter


@dataclass
class EngineConfig:
    session_id: str
    max_rounds: int = 50
    system_prompt: str = ""
    task_goal: str = ""


def serialize_message(msg: Message) -> dict[str, Any]:
    """Convert a Message to a JSON-serialisable dict for API responses."""
    blocks = []
    for b in msg.content:
        d: dict[str, Any] = {"type": b.type}
        if hasattr(b, "text"):
            d["text"] = b.text
        if hasattr(b, "thinking"):
            d["thinking"] = b.thinking
        if hasattr(b, "tool_call_id"):
            d["tool_call_id"] = b.tool_call_id
        if hasattr(b, "tool_name"):
            d["tool_name"] = b.tool_name
        if hasattr(b, "tool_input"):
            d["tool_input"] = b.tool_input
        if hasattr(b, "content"):
            d["content"] = b.content
        if hasattr(b, "is_error"):
            d["is_error"] = b.is_error
        blocks.append(d)
    return {
        "role": msg.role,
        "content": blocks,
        "round_index": msg.round_index,
        "is_compressed": msg.is_compressed,
    }


class AgentEngine:
    def __init__(
        self,
        config: EngineConfig,
        loop: ReactLoop,
        session_store: SessionStore,
        emitter: EventEmitter,
    ) -> None:
        self._config = config
        self._loop = loop
        self._session_store = session_store
        self._emitter = emitter

        self._sm = StateMachine()
        self._messages: list[Message] = []
        self._state_lock = asyncio.Lock()
        self._cancel_event = asyncio.Event()
        self._intervention_queue: asyncio.Queue[Message] = asyncio.Queue()
        self._last_error: str = ""
        self._message_listeners: list[MessageListener] = []
        self._token_listeners: list[TokenCallback] = []
        self._state_listeners: list[StateListener] = []

        # Inject system prompt if provided
        if config.system_prompt:
            self._messages.append(
                Message(
                    role="system",
                    content=[TextBlock(text=config.system_prompt)],
                )
            )

    @property
    def session_id(self) -> str:
        return self._config.session_id

    # ──────────────────────────────────────────────────────────────────
    # Public API (called by REST layer or tests)
    # ──────────────────────────────────────────────────────────────────

    def add_message_listener(self, listener: MessageListener) -> None:
        """Register a callback invoked for every new message (real-time push)."""
        self._message_listeners.append(listener)

    def remove_message_listener(self, listener: MessageListener) -> None:
        """Unregister a previously added listener."""
        try:
            self._message_listeners.remove(listener)
        except ValueError:
            pass

    def add_token_listener(self, listener: TokenCallback) -> None:
        """Register a callback invoked for each streamed text token."""
        self._token_listeners.append(listener)

    def remove_token_listener(self, listener: TokenCallback) -> None:
        """Unregister a previously added token listener."""
        try:
            self._token_listeners.remove(listener)
        except ValueError:
            pass

    def add_state_listener(self, listener: StateListener) -> None:
        """Register a callback invoked when engine state changes (e.g. RUNNING → COMPLETED)."""
        self._state_listeners.append(listener)

    def remove_state_listener(self, listener: StateListener) -> None:
        """Unregister a previously added state listener."""
        try:
            self._state_listeners.remove(listener)
        except ValueError:
            pass

    async def get_snapshot(self) -> dict[str, Any]:
        """
        Frontend polling endpoint — returns state + last 20 messages atomically.
        Backend is the single source of truth; never cache this on the frontend.
        """
        async with self._state_lock:
            return {
                "session_id": self._config.session_id,
                "state": self._sm.state.name,
                "is_running": self._sm.state == EngineState.RUNNING,
                "last_error": self._last_error,
                "last_messages": [
                    serialize_message(m) for m in self._messages[-20:]
                ],
            }

    async def send_message(self, text: str) -> None:
        """
        Accept a user message.
        If engine is RUNNING, queue the message as an intervention.
        Otherwise transition to RUNNING and fire off the loop.
        """
        async with self._state_lock:
            state = self._sm.state

        if state == EngineState.RUNNING:
            # Queue — will be injected after the current tool_result flushes
            await self._intervention_queue.put(
                Message(role="user", content=[TextBlock(text=text)])
            )
            self._emitter.emit(
                "send_message", "triggered-intercepted",
                detail={"reason": "engine_running", "queued": True},
            )
            return

        user_msg = Message(role="user", content=[TextBlock(text=text)])

        # Concurrency rule: transition inside lock, then release before async work
        async with self._state_lock:
            # Session reuse: COMPLETED -> WAITING_INPUT implicitly before starting again
            if self._sm.state == EngineState.COMPLETED:
                self._sm.transition(EngineState.WAITING_INPUT)
            self._messages.append(user_msg)
            self._sm.transition(EngineState.RUNNING)
            self._emitter.emit(
                "state_transition", "triggered-executed",
                detail={"to": EngineState.RUNNING.name},
            )

        # Fire-and-forget — all three outcome paths guarantee state restoration
        asyncio.create_task(self._run_loop_guarded())

    async def cancel(self) -> None:
        """Signal the running loop to stop at the next round boundary."""
        self._cancel_event.set()
        self._emitter.emit("cancel_requested", "triggered-executed", detail={})

    async def confirm(self) -> None:
        """Approve a pending tool action (WAITING_CONFIRMATION → RUNNING)."""
        async with self._state_lock:
            if self._sm.state == EngineState.WAITING_CONFIRMATION:
                self._sm.transition(EngineState.RUNNING)
                self._emitter.emit(
                    "state_transition", "triggered-executed",
                    detail={"to": EngineState.RUNNING.name, "via": "confirm"},
                )

    async def deny(self) -> None:
        """Deny a pending tool action (WAITING_CONFIRMATION → WAITING_INPUT)."""
        async with self._state_lock:
            if self._sm.state == EngineState.WAITING_CONFIRMATION:
                self._sm.transition(EngineState.WAITING_INPUT)
                self._emitter.emit(
                    "state_transition", "triggered-executed",
                    detail={"to": EngineState.WAITING_INPUT.name, "via": "deny"},
                )

    # ──────────────────────────────────────────────────────────────────
    # Internal
    # ──────────────────────────────────────────────────────────────────

    async def _notify_state_listeners(self) -> None:
        """Notify all registered state listeners. Called outside the state lock."""
        for listener in list(self._state_listeners):
            try:
                await listener()
            except Exception:
                pass

    async def _run_loop_guarded(self) -> None:
        """
        Wraps ReactLoop.run() and guarantees state is restored on all paths.
        Never let an exception escape without transitioning out of RUNNING.
        """
        try:
            await self._loop.run(
                messages=self._messages,
                cancel_event=self._cancel_event,
                intervention_queue=self._intervention_queue,
                on_message=self._on_message,
                on_token=self._on_token,
            )
            async with self._state_lock:
                self._sm.transition(EngineState.COMPLETED)
                self._emitter.emit(
                    "state_transition", "triggered-executed",
                    detail={"to": EngineState.COMPLETED.name},
                )
            await self._notify_state_listeners()

        except asyncio.CancelledError:
            async with self._state_lock:
                self._sm.transition(EngineState.WAITING_INPUT)
                self._emitter.emit(
                    "state_transition", "triggered-executed",
                    detail={"to": EngineState.WAITING_INPUT.name, "via": "cancel"},
                )
            await self._notify_state_listeners()
            # Do not re-raise — we handled it gracefully

        except Exception as exc:
            import traceback
            self._last_error = traceback.format_exc()
            async with self._state_lock:
                self._sm.transition(EngineState.ERROR)
            self._emitter.emit_error(
                "engine_loop_error", str(exc),
            )
            await self._notify_state_listeners()

        finally:
            # Always clear the cancel signal and persist messages
            self._cancel_event.clear()
            try:
                await self._session_store.save(
                    self._config.session_id, self._messages
                )
            except Exception as exc:
                self._emitter.emit_error("session_save_error", str(exc))

    async def _on_message(self, msg: Message) -> None:
        """Called by ReactLoop for every new message (assistant or tool)."""
        async with self._state_lock:
            self._messages.append(msg)
        # Notify listeners outside the lock — they may do I/O (e.g. WebSocket send)
        for listener in list(self._message_listeners):
            try:
                await listener(msg)
            except Exception:
                pass  # never let a broken listener crash the loop

    async def _on_token(self, text: str) -> None:
        """Called by ReactLoop for each streamed text token."""
        for listener in list(self._token_listeners):
            try:
                await listener(text)
            except Exception as exc:
                self._emitter.emit_error("token_listener_error", str(exc))
