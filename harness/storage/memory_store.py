from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class MemoryEntry:
    entry_id: str
    content: str
    scope: str = "global"
    tags: list[str] = field(default_factory=list)
    created_by_session: str = ""
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)


class MemoryStore(ABC):
    @abstractmethod
    async def add(
        self,
        content: str,
        scope: str = "global",
        tags: list[str] | None = None,
        created_by_session: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> MemoryEntry: ...

    @abstractmethod
    async def get(self, entry_id: str) -> MemoryEntry | None: ...

    @abstractmethod
    async def search(
        self,
        query: str = "",
        scope: str = "",
        tags: list[str] | None = None,
        limit: int = 20,
    ) -> list[MemoryEntry]: ...

    @abstractmethod
    async def delete(self, entry_id: str) -> bool: ...
