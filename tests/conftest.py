"""Shared fixtures for the test suite."""
from __future__ import annotations

import asyncio
import pytest

from harness.observability.events import EventEmitter
from harness.storage.backends.memory import MemorySessionStore, MemoryCheckpointStore
from harness.tools.overflow import OverflowStore
from harness.tools.registry import ToolRegistry


@pytest.fixture
def session_id() -> str:
    return "test-session-001"


@pytest.fixture
def emitter(session_id: str) -> EventEmitter:
    return EventEmitter(session_id)


@pytest.fixture
def session_store() -> MemorySessionStore:
    return MemorySessionStore()


@pytest.fixture
def checkpoint_store() -> MemoryCheckpointStore:
    return MemoryCheckpointStore()


@pytest.fixture
def tool_registry() -> ToolRegistry:
    return ToolRegistry()


@pytest.fixture
def overflow_store() -> OverflowStore:
    return OverflowStore()
