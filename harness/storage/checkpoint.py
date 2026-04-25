from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from harness.types.messages import Message
from harness.engine.state_machine import EngineState

@dataclass
class Checkpoint:
    session_id: str
    checkpoint_id: str
    round_index: int
    state: EngineState
    messages: list[Message]
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class CheckpointStore(ABC):
    @abstractmethod
    async def save(self, checkpoint: Checkpoint) -> str:
        """Persist checkpoint. Returns checkpoint_id."""

    @abstractmethod
    async def load(self, checkpoint_id: str) -> Checkpoint | None: ...

    @abstractmethod
    async def list_for_session(self, session_id: str) -> list[str]: ...

    @abstractmethod
    async def delete(self, checkpoint_id: str) -> None: ...
