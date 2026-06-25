from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from harness.types.messages import Message

@dataclass
class SessionRecord:
    session_id: str
    messages: list[Message]
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict = field(default_factory=dict)
    display_name: str = ""
    pinned: bool = False
    archived: bool = False

class SessionStore(ABC):
    @abstractmethod
    async def save(self, session_id: str, messages: list[Message]) -> None: ...

    @abstractmethod
    async def load(self, session_id: str) -> SessionRecord | None: ...

    @abstractmethod
    async def list_sessions(self) -> list[SessionRecord]: ...

    @abstractmethod
    async def delete(self, session_id: str) -> None: ...

    @abstractmethod
    async def update_metadata(self, session_id: str, **kwargs) -> None: ...
