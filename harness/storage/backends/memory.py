from __future__ import annotations
import uuid
from datetime import datetime, timezone
from harness.types.messages import Message
from harness.storage.session import SessionStore, SessionRecord
from harness.storage.checkpoint import CheckpointStore, Checkpoint

class MemorySessionStore(SessionStore):
    def __init__(self) -> None:
        self._sessions: dict[str, SessionRecord] = {}

    async def save(self, session_id: str, messages: list[Message], title: str = "", metadata: dict | None = None) -> None:
        now = datetime.now(timezone.utc).isoformat()
        if session_id in self._sessions:
            rec = self._sessions[session_id]
            rec.messages = list(messages)
            rec.updated_at = now
            if title:
                rec.title = title
            if metadata is not None:
                rec.metadata = metadata
        else:
            self._sessions[session_id] = SessionRecord(
                session_id=session_id,
                messages=list(messages),
                created_at=now,
                updated_at=now,
                title=title,
                metadata=metadata if metadata is not None else {},
            )

    async def load(self, session_id: str) -> SessionRecord | None:
        return self._sessions.get(session_id)

    async def list_sessions(self) -> list[SessionRecord]:
        records = list(self._sessions.values())
        # Newest first, then pinned on top (stable sort)
        records.sort(key=lambda r: r.created_at, reverse=True)
        records.sort(key=lambda r: r.pinned, reverse=True)
        return records

    async def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    async def update_metadata(self, session_id: str, **kwargs) -> None:
        rec = self._sessions.get(session_id)
        if rec is None:
            return
        for k, v in kwargs.items():
            if k == "pinned":
                rec.pinned = bool(v)
            elif k == "archived":
                rec.archived = bool(v)
            elif k == "display_name":
                rec.display_name = str(v)


class MemoryCheckpointStore(CheckpointStore):
    def __init__(self) -> None:
        self._checkpoints: dict[str, Checkpoint] = {}
        self._by_session: dict[str, list[str]] = {}

    async def save(self, checkpoint: Checkpoint) -> str:
        cid = checkpoint.checkpoint_id or str(uuid.uuid4())
        checkpoint.checkpoint_id = cid
        self._checkpoints[cid] = checkpoint
        self._by_session.setdefault(checkpoint.session_id, []).append(cid)
        return cid

    async def load(self, checkpoint_id: str) -> Checkpoint | None:
        return self._checkpoints.get(checkpoint_id)

    async def list_for_session(self, session_id: str) -> list[str]:
        return list(self._by_session.get(session_id, []))

    async def delete(self, checkpoint_id: str) -> None:
        cp = self._checkpoints.pop(checkpoint_id, None)
        if cp:
            lst = self._by_session.get(cp.session_id, [])
            if checkpoint_id in lst:
                lst.remove(checkpoint_id)
