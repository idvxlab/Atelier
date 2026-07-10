from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class PlanItem:
    item_id: str
    content: str
    status: str = "pending"
    assigned_session_id: str = ""
    result_message_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_todo_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "content": self.content,
            "status": self.status,
            "assigned_session_id": self.assigned_session_id,
            "result_message_id": self.result_message_id,
        }


@dataclass
class PlanState:
    plan_id: str
    session_id: str
    title: str = ""
    status: str = "pending"
    items: list[PlanItem] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "session_id": self.session_id,
            "title": self.title,
            "status": self.status,
            "items": [item.to_todo_dict() for item in self.items],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": dict(self.metadata),
        }

    def to_todos(self) -> list[dict[str, Any]]:
        return [item.to_todo_dict() for item in self.items]


class PlanStore(ABC):
    @abstractmethod
    async def save_plan(self, plan: PlanState) -> None: ...

    @abstractmethod
    async def load_by_session(self, session_id: str) -> PlanState | None: ...

    @abstractmethod
    async def bind_item(
        self,
        plan_id: str,
        item_id: str,
        assigned_session_id: str = "",
        result_message_id: str = "",
    ) -> bool: ...

    @abstractmethod
    async def delete_by_session(self, session_id: str) -> None: ...
