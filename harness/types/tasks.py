from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class TaskStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskRecord:
    task_id: str
    session_id: str
    title: str
    status: TaskStatus
    source: str
    parent_session_id: str = ""
    related_session_id: str = ""
    plan_item_id: str = ""
    index: int | None = None
    created_at: str = ""
    updated_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "session_id": self.session_id,
            "title": self.title,
            "status": self.status.value,
            "source": self.source,
            "parent_session_id": self.parent_session_id,
            "related_session_id": self.related_session_id,
            "plan_item_id": self.plan_item_id,
            "index": self.index,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": dict(self.metadata),
        }


def timestamp_to_iso(value: float | int | None) -> str:
    if not value:
        return ""
    return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat()


def plan_status_to_task_status(status: str) -> TaskStatus:
    if status == "completed":
        return TaskStatus.COMPLETED
    if status == "in_progress":
        return TaskStatus.RUNNING
    return TaskStatus.PENDING


def build_task_records(
    session_id: str,
    todos: list[dict[str, Any]] | None = None,
    pending_commands: list[dict[str, Any]] | None = None,
    pending_spawns: list[dict[str, Any]] | None = None,
) -> list[TaskRecord]:
    records: list[TaskRecord] = []

    for idx, item in enumerate(todos or []):
        item_id = str(item.get("item_id") or f"item_{idx + 1}")
        records.append(
            TaskRecord(
                task_id=f"plan:{session_id}:{item_id}",
                session_id=session_id,
                title=str(item.get("content", "")),
                status=plan_status_to_task_status(str(item.get("status", "pending"))),
                source="plan_item",
                related_session_id=str(item.get("assigned_session_id", "")),
                plan_item_id=item_id,
                index=idx,
                metadata={
                    "result_message_id": str(item.get("result_message_id", "")),
                },
            )
        )

    for command in pending_commands or []:
        index = int(command.get("index", 0) or 0)
        records.append(
            TaskRecord(
                task_id=f"queue:{session_id}:{index}",
                session_id=session_id,
                title=str(command.get("text", "")),
                status=TaskStatus.QUEUED,
                source="queued_command",
                index=index,
                created_at=timestamp_to_iso(command.get("submitted_at")),
            )
        )

    for spawn in pending_spawns or []:
        index = int(spawn.get("index", 0) or 0)
        sub_id = str(spawn.get("sub_id", ""))
        records.append(
            TaskRecord(
                task_id=f"spawn:{session_id}:{sub_id or index}",
                session_id=session_id,
                title=str(spawn.get("display_name") or spawn.get("task", "")),
                status=TaskStatus.RUNNING,
                source="subagent",
                parent_session_id=session_id,
                related_session_id=sub_id,
                index=index,
                created_at=timestamp_to_iso(spawn.get("submitted_at")),
                metadata={"task": str(spawn.get("task", ""))},
            )
        )

    return records
