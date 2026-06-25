"""
Lightweight Prompt Cache — avoids re-constructing static prompt fragments
on every round.

Cache layers
============
  1. system_prompt  — the static base: system_prompt + skills + reasoning +
     recovery instructions.  Built once at engine init.  Immutable.
  2. tool_schemas   — list of ToolSchema objects.  Built once when the
     tool registry stabilises.  Only refreshed when `refresh_tool_schemas()`
     is called (rare — only if the registry changes at runtime).
  3. mode_blocks    — the question / noquestion instruction block.  One
     entry per mode, built once, refreshed when `set_question_mode()` is
     called at runtime.

Why not cache the full system message?
======================================
The system message injected into _messages[0] is the concatenation of (1) +
(3).  We deliberately do NOT cache the concatenated string because:
  - The engine mutates the system TextBlock.text in-place when the user
    toggles question_mode at runtime (`_restamp_system_prompt_for_question_mode`).
  - Caching the concatenated string would create a stale copy that the engine
    would have to re-assemble anyway.
Instead, callers compose (1) + (3) and write the result into the message
list once.  Subsequent reads are always from the live message list, so the
in-place mutation is always visible with zero cache-coherence work.

This module therefore caches the *fragments*, not the assembled result.

Cache invalidation
==================
  - system_prompt  : never (immutable — base instructions never change)
  - tool_schemas   : call `refresh_tool_schemas()` after registry mutation
  - mode_blocks    : call `invalidate_mode()` + `set_question_mode()`;
                     `_restamp_system_prompt_for_question_mode` calls these
                     automatically when the engine toggles mode at runtime
"""
from __future__ import annotations

import threading
from typing import Any, Generic, TypeVar

T = TypeVar("T")

# Thread-safety note:
# AgentEngine is single-threaded (all calls are async, no OS threads touch
# the cache concurrently).  The lock below is purely to satisfy static type
# checkers.  In practice it is never contended.
_cache_lock = threading.Lock()


class PromptCache:
    """
    Simple key-value cache for stable prompt fragments.

    Thread-safe via a threading.Lock (not asyncio.Lock, because this object
    is also read by synchronous code paths in factory.py at construction time).
    """
    __slots__ = (
        "_system_prompt",
        "_tool_schemas",
        "_mode_blocks",
    )

    def __init__(self) -> None:
        self._system_prompt: str | None = None
        self._tool_schemas: list[Any] | None = None  # list[ToolSchema]
        self._mode_blocks: dict[str, str] = {}

    # ── system_prompt ────────────────────────────────────────────────────

    def set_system_prompt(self, text: str) -> None:
        """Cache the immutable static base (system_prompt + skills + reasoning)."""
        with _cache_lock:
            self._system_prompt = text

    def get_system_prompt(self) -> str | None:
        with _cache_lock:
            return self._system_prompt

    # ── tool_schemas ─────────────────────────────────────────────────────

    def set_tool_schemas(self, schemas: list[Any]) -> None:
        """Cache the ToolSchema list (built once after registry stabilises)."""
        with _cache_lock:
            self._tool_schemas = schemas

    def get_tool_schemas(self) -> list[Any] | None:
        """Return the cached list, or None if not yet populated."""
        with _cache_lock:
            return self._tool_schemas

    def refresh_tool_schemas(self) -> None:
        """Drop the cached tool schemas (call after registry mutation)."""
        with _cache_lock:
            self._tool_schemas = None

    # ── mode_blocks ───────────────────────────────────────────────────────

    def set_mode_block(self, mode: str, text: str) -> None:
        """Cache the question/noquestion instruction block for a mode."""
        with _cache_lock:
            self._mode_blocks[mode] = text

    def get_mode_block(self, mode: str) -> str | None:
        with _cache_lock:
            return self._mode_blocks.get(mode)

    def invalidate_mode(self, mode: str) -> None:
        """Drop the cached block for a mode."""
        with _cache_lock:
            self._mode_blocks.pop(mode, None)

    def invalidate_all_modes(self) -> None:
        with _cache_lock:
            self._mode_blocks.clear()
