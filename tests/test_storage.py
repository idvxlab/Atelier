"""Tests for storage backends."""
from __future__ import annotations

import pytest

from harness.engine.state_machine import EngineState
from harness.storage.backends.memory import MemorySessionStore, MemoryCheckpointStore
from harness.storage.checkpoint import Checkpoint
from harness.types.messages import Message, TextBlock


def _msg(text: str, role: str = "user") -> Message:
    return Message(role=role, content=[TextBlock(text=text)])


# ──────────────────────────────────────────────────────────────────────
# MemorySessionStore
# ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_session_save_and_load():
    store = MemorySessionStore()
    msgs = [_msg("Hello"), _msg("World", role="assistant")]
    await store.save("s1", msgs)
    record = await store.load("s1")
    assert record is not None
    assert len(record.messages) == 2
    assert record.session_id == "s1"


@pytest.mark.asyncio
async def test_session_load_nonexistent():
    store = MemorySessionStore()
    assert await store.load("missing") is None


@pytest.mark.asyncio
async def test_session_overwrite():
    store = MemorySessionStore()
    await store.save("s1", [_msg("v1")])
    await store.save("s1", [_msg("v2"), _msg("v3")])
    record = await store.load("s1")
    assert len(record.messages) == 2


@pytest.mark.asyncio
async def test_session_list():
    store = MemorySessionStore()
    await store.save("a", [])
    await store.save("b", [])
    sessions = await store.list_sessions()
    ids = [s.session_id for s in sessions]
    assert "a" in ids
    assert "b" in ids


@pytest.mark.asyncio
async def test_session_delete():
    store = MemorySessionStore()
    await store.save("s1", [_msg("Hi")])
    await store.delete("s1")
    assert await store.load("s1") is None


# ──────────────────────────────────────────────────────────────────────
# MemoryCheckpointStore
# ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_checkpoint_save_and_load():
    store = MemoryCheckpointStore()
    cp = Checkpoint(
        session_id="s1",
        checkpoint_id="",
        round_index=5,
        state=EngineState.RUNNING,
        messages=[_msg("checkpoint msg")],
    )
    cid = await store.save(cp)
    assert cid != ""
    loaded = await store.load(cid)
    assert loaded is not None
    assert loaded.round_index == 5
    assert loaded.state == EngineState.RUNNING


@pytest.mark.asyncio
async def test_checkpoint_list_for_session():
    store = MemoryCheckpointStore()
    for i in range(3):
        cp = Checkpoint(
            session_id="s1",
            checkpoint_id=f"cp-{i}",
            round_index=i,
            state=EngineState.RUNNING,
            messages=[],
        )
        await store.save(cp)
    ids = await store.list_for_session("s1")
    assert len(ids) == 3


@pytest.mark.asyncio
async def test_checkpoint_delete():
    store = MemoryCheckpointStore()
    cp = Checkpoint(
        session_id="s1",
        checkpoint_id="to-delete",
        round_index=0,
        state=EngineState.COMPLETED,
        messages=[],
    )
    cid = await store.save(cp)
    await store.delete(cid)
    assert await store.load(cid) is None
