from __future__ import annotations
import uuid
from datetime import datetime, timezone
from harness.types.messages import Message
from harness.storage.session import SessionStore, SessionRecord
from harness.storage.checkpoint import CheckpointStore, Checkpoint
from harness.storage.memory_store import MemoryEntry, MemoryStore, utc_now
from harness.storage.plan_store import PlanState, PlanStore

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


class InMemoryMemoryStore(MemoryStore):
    def __init__(self) -> None:
        self._entries: dict[str, MemoryEntry] = {}

    async def add(
        self,
        content: str,
        scope: str = "global",
        tags: list[str] | None = None,
        created_by_session: str = "",
        metadata: dict | None = None,
    ) -> MemoryEntry:
        now = utc_now()
        entry = MemoryEntry(
            entry_id=f"mem_{uuid.uuid4().hex[:12]}",
            content=content,
            scope=scope or "global",
            tags=list(tags or []),
            created_by_session=created_by_session,
            created_at=now,
            updated_at=now,
            metadata=dict(metadata or {}),
        )
        self._entries[entry.entry_id] = entry
        return entry

    async def get(self, entry_id: str) -> MemoryEntry | None:
        return self._entries.get(entry_id)

    async def search(
        self,
        query: str = "",
        scope: str = "",
        tags: list[str] | None = None,
        limit: int = 20,
    ) -> list[MemoryEntry]:
        q = query.casefold().strip()
        wanted_tags = {t.casefold() for t in (tags or []) if t}
        results: list[MemoryEntry] = []
        for entry in self._entries.values():
            if scope and entry.scope != scope:
                continue
            if wanted_tags and not wanted_tags.issubset({t.casefold() for t in entry.tags}):
                continue
            haystack = " ".join([entry.content, entry.scope, " ".join(entry.tags)]).casefold()
            if q and q not in haystack:
                continue
            results.append(entry)
        results.sort(key=lambda e: e.updated_at, reverse=True)
        return results[: max(1, min(limit, 100))]

    async def delete(self, entry_id: str) -> bool:
        return self._entries.pop(entry_id, None) is not None


class InMemoryPlanStore(PlanStore):
    def __init__(self) -> None:
        self._plans: dict[str, PlanState] = {}
        self._by_session: dict[str, str] = {}

    async def save_plan(self, plan: PlanState) -> None:
        self._plans[plan.plan_id] = plan
        self._by_session[plan.session_id] = plan.plan_id

    async def load_by_session(self, session_id: str) -> PlanState | None:
        plan_id = self._by_session.get(session_id)
        if not plan_id:
            return None
        return self._plans.get(plan_id)

    async def bind_item(
        self,
        plan_id: str,
        item_id: str,
        assigned_session_id: str = "",
        result_message_id: str = "",
    ) -> bool:
        plan = self._plans.get(plan_id)
        if plan is None:
            return False
        for item in plan.items:
            if item.item_id == item_id:
                if assigned_session_id:
                    item.assigned_session_id = assigned_session_id
                if result_message_id:
                    item.result_message_id = result_message_id
                plan.updated_at = utc_now()
                return True
        return False

    async def delete_by_session(self, session_id: str) -> None:
        plan_id = self._by_session.pop(session_id, None)
        if plan_id:
            self._plans.pop(plan_id, None)
