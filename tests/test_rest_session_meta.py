from __future__ import annotations

import pytest

import api.rest as rest_mod
from harness.storage.backends.memory import MemorySessionStore


class _FakeEngine:
    async def get_snapshot(self):
        return {
            "session_id": "sub_test",
            "agent_id": "design-primary",
            "meta": {},
        }


@pytest.mark.asyncio
async def test_get_state_prefers_persisted_subagent_identity_metadata():
    previous_store = rest_mod._session_store
    previous_engines = rest_mod._engines
    previous_meta = rest_mod._engine_meta

    store = MemorySessionStore()
    await store.save(
        "sub_test",
        [],
        metadata={
            "persona": "design-research",
            "provider": "openai-hub",
            "spawn_depth": 1,
            "parent_session_id": "parent_test",
        },
    )

    rest_mod._session_store = store
    rest_mod._engines = {"sub_test": _FakeEngine()}
    rest_mod._engine_meta = {
        "sub_test": {
            "persona": "design-primary",
            "provider": "openai-hub",
        }
    }

    try:
        snapshot = await rest_mod.get_state("sub_test")
    finally:
        rest_mod._session_store = previous_store
        rest_mod._engines = previous_engines
        rest_mod._engine_meta = previous_meta

    assert snapshot["meta"]["persona"] == "design-research"
    assert snapshot["meta"]["spawn_depth"] == 1
    assert snapshot["meta"]["parent_session_id"] == "parent_test"
