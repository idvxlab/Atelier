from __future__ import annotations
import uuid

class OverflowStore:
    """
    In-memory store for oversized tool outputs.
    Returns a ref_id; the tool result message contains "ref:<id>" instead
    of the full output.
    """
    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def store(self, content: str) -> str:
        ref_id = str(uuid.uuid4())
        self._store[ref_id] = content
        return ref_id

    async def retrieve(self, ref_id: str) -> str | None:
        return self._store.get(ref_id)
