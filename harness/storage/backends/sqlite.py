"""
SQLite-backed persistent storage using aiosqlite.

Schema
------
sessions
  session_id  TEXT PRIMARY KEY
  messages    TEXT  -- JSON blob: list[MessageDict]
  created_at  TEXT
  updated_at  TEXT
  metadata    TEXT  -- JSON blob: dict

checkpoints
  checkpoint_id  TEXT PRIMARY KEY
  session_id     TEXT NOT NULL
  round_index    INTEGER NOT NULL
  state          TEXT NOT NULL  -- EngineState.name
  messages       TEXT NOT NULL  -- JSON blob: list[MessageDict]
  created_at     TEXT NOT NULL

MessageDict wire format
-----------------------
{
  "role": str,
  "round_index": int,
  "is_compressed": bool,
  "content": [
    {"type": "text",         "text": str}
    {"type": "thinking",     "thinking": str, "signature": str}
    {"type": "tool_call",    "tool_call_id": str, "tool_name": str, "tool_input": dict}
    {"type": "tool_result",  "tool_call_id": str, "content": str,
                             "is_error": bool, "is_overflow_ref": bool}
  ]
}
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

import aiosqlite

from harness.types.messages import (
    Message,
    TextBlock,
    ThinkingBlock,
    ToolCallBlock,
    ToolResultBlock,
)
from harness.engine.state_machine import EngineState
from harness.storage.session import SessionStore, SessionRecord
from harness.storage.checkpoint import CheckpointStore, Checkpoint


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

def _block_to_dict(block: Any) -> dict:
    """Convert a single content block to a plain dict for JSON storage."""
    t = block.type
    if t == "text":
        return {"type": "text", "text": block.text}
    if t == "thinking":
        return {"type": "thinking", "thinking": block.thinking, "signature": block.signature}
    if t == "tool_call":
        return {
            "type": "tool_call",
            "tool_call_id": block.tool_call_id,
            "tool_name": block.tool_name,
            "tool_input": block.tool_input,
        }
    if t == "tool_result":
        return {
            "type": "tool_result",
            "tool_call_id": block.tool_call_id,
            "content": block.content,
            "is_error": block.is_error,
            "is_overflow_ref": block.is_overflow_ref,
        }
    raise ValueError(f"Unknown block type: {t!r}")


def _block_from_dict(d: dict) -> Any:
    """Reconstruct the correct block dataclass from a plain dict."""
    t = d["type"]
    if t == "text":
        return TextBlock(text=d["text"])
    if t == "thinking":
        return ThinkingBlock(thinking=d["thinking"], signature=d.get("signature", ""))
    if t == "tool_call":
        return ToolCallBlock(
            tool_call_id=d["tool_call_id"],
            tool_name=d["tool_name"],
            tool_input=d.get("tool_input", {}),
        )
    if t == "tool_result":
        return ToolResultBlock(
            tool_call_id=d["tool_call_id"],
            content=d["content"],
            is_error=d.get("is_error", False),
            is_overflow_ref=d.get("is_overflow_ref", False),
        )
    raise ValueError(f"Unknown block type in stored data: {t!r}")


def _messages_to_json(messages: list[Message]) -> str:
    """Serialise a list of Message objects to a JSON string."""
    data = [
        {
            "role": msg.role,
            "round_index": msg.round_index,
            "is_compressed": msg.is_compressed,
            "content": [_block_to_dict(b) for b in msg.content],
        }
        for msg in messages
    ]
    return json.dumps(data, ensure_ascii=False)


def _messages_from_json(raw: str) -> list[Message]:
    """Deserialise a JSON string produced by _messages_to_json back to Message objects."""
    data = json.loads(raw)
    messages: list[Message] = []
    for item in data:
        blocks = [_block_from_dict(b) for b in item["content"]]
        messages.append(
            Message(
                role=item["role"],
                content=blocks,
                round_index=item.get("round_index", 0),
                is_compressed=item.get("is_compressed", False),
            )
        )
    return messages


# ---------------------------------------------------------------------------
# SQLiteSessionStore
# ---------------------------------------------------------------------------

class SQLiteSessionStore(SessionStore):
    """Persistent session store backed by a SQLite database file."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._initialised = False

    async def _ensure_tables(self, conn: aiosqlite.Connection) -> None:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id  TEXT PRIMARY KEY,
                messages    TEXT NOT NULL DEFAULT '[]',
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL,
                metadata    TEXT NOT NULL DEFAULT '{}'
            )
        """)
        # Schema migrations — add columns that may not exist in older DBs
        for col, col_def in [
            ("display_name", "TEXT DEFAULT ''"),
            ("pinned", "INTEGER DEFAULT 0"),
            ("archived", "INTEGER DEFAULT 0"),
        ]:
            try:
                await conn.execute(
                    f"ALTER TABLE sessions ADD COLUMN {col} {col_def}"
                )
            except aiosqlite.OperationalError:
                pass  # column already exists
        await conn.commit()

    async def _get_conn(self) -> aiosqlite.Connection:
        conn = await aiosqlite.connect(self._db_path)
        conn.row_factory = aiosqlite.Row
        await self._ensure_tables(conn)
        return conn

    async def save(self, session_id: str, messages: list[Message]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        messages_json = _messages_to_json(messages)
        async with aiosqlite.connect(self._db_path) as conn:
            conn.row_factory = aiosqlite.Row
            await self._ensure_tables(conn)
            # Upsert: insert or update. Preserve existing metadata/display_name/pinned/archived on conflict.
            await conn.execute("""
                INSERT INTO sessions (session_id, messages, created_at, updated_at, metadata)
                VALUES (?, ?, ?, ?, '{}')
                ON CONFLICT(session_id) DO UPDATE SET
                    messages   = excluded.messages,
                    updated_at = excluded.updated_at
            """, (session_id, messages_json, now, now))
            await conn.commit()

    async def load(self, session_id: str) -> SessionRecord | None:
        async with aiosqlite.connect(self._db_path) as conn:
            conn.row_factory = aiosqlite.Row
            await self._ensure_tables(conn)
            async with conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
            ) as cursor:
                row = await cursor.fetchone()
            if row is None:
                return None
            return SessionRecord(
                session_id=row["session_id"],
                messages=_messages_from_json(row["messages"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                metadata=json.loads(row["metadata"]),
                display_name=row["display_name"] if "display_name" in row.keys() else "",
                pinned=bool(row["pinned"]) if "pinned" in row.keys() else False,
                archived=bool(row["archived"]) if "archived" in row.keys() else False,
            )

    async def list_sessions(self) -> list[SessionRecord]:
        async with aiosqlite.connect(self._db_path) as conn:
            conn.row_factory = aiosqlite.Row
            await self._ensure_tables(conn)
            async with conn.execute(
                "SELECT * FROM sessions ORDER BY pinned DESC, created_at DESC"
            ) as cur:
                rows = await cur.fetchall()
            results: list[SessionRecord] = []
            for row in rows:
                results.append(SessionRecord(
                    session_id=row["session_id"],
                    messages=[],  # lazy — messages not needed for listing
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    metadata=json.loads(row["metadata"]),
                    display_name=row["display_name"] if "display_name" in row.keys() else "",
                    pinned=bool(row["pinned"]) if "pinned" in row.keys() else False,
                    archived=bool(row["archived"]) if "archived" in row.keys() else False,
                ))
            return results

    async def update_metadata(self, session_id: str, **kwargs) -> None:
        """Partially update session metadata fields (display_name, pinned, archived)."""
        allowed = {"display_name", "pinned", "archived"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return
        set_clauses: list[str] = []
        params: list[Any] = []
        for k, v in updates.items():
            if k == "pinned":
                set_clauses.append("pinned = ?")
                params.append(1 if v else 0)
            elif k == "archived":
                set_clauses.append("archived = ?")
                params.append(1 if v else 0)
            else:
                set_clauses.append(f"{k} = ?")
                params.append(v)
        params.append(session_id)
        async with aiosqlite.connect(self._db_path) as conn:
            await self._ensure_tables(conn)
            await conn.execute(
                f"UPDATE sessions SET {', '.join(set_clauses)} WHERE session_id = ?",
                params,
            )
            await conn.commit()

    async def delete(self, session_id: str) -> None:
        async with aiosqlite.connect(self._db_path) as conn:
            await self._ensure_tables(conn)
            await conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            await conn.commit()


# ---------------------------------------------------------------------------
# SQLiteCheckpointStore
# ---------------------------------------------------------------------------

class SQLiteCheckpointStore(CheckpointStore):
    """Persistent checkpoint store backed by a SQLite database file."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    async def _ensure_tables(self, conn: aiosqlite.Connection) -> None:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS checkpoints (
                checkpoint_id  TEXT PRIMARY KEY,
                session_id     TEXT NOT NULL,
                round_index    INTEGER NOT NULL,
                state          TEXT NOT NULL,
                messages       TEXT NOT NULL DEFAULT '[]',
                created_at     TEXT NOT NULL
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_checkpoints_session
            ON checkpoints (session_id)
        """)
        await conn.commit()

    async def save(self, checkpoint: Checkpoint) -> str:
        cid = checkpoint.checkpoint_id or str(uuid.uuid4())
        checkpoint.checkpoint_id = cid
        messages_json = _messages_to_json(checkpoint.messages)
        state_name = checkpoint.state.name  # store enum by name, e.g. "RUNNING"
        async with aiosqlite.connect(self._db_path) as conn:
            conn.row_factory = aiosqlite.Row
            await self._ensure_tables(conn)
            await conn.execute("""
                INSERT INTO checkpoints
                    (checkpoint_id, session_id, round_index, state, messages, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(checkpoint_id) DO UPDATE SET
                    session_id  = excluded.session_id,
                    round_index = excluded.round_index,
                    state       = excluded.state,
                    messages    = excluded.messages,
                    created_at  = excluded.created_at
            """, (cid, checkpoint.session_id, checkpoint.round_index,
                  state_name, messages_json, checkpoint.created_at))
            await conn.commit()
        return cid

    async def load(self, checkpoint_id: str) -> Checkpoint | None:
        async with aiosqlite.connect(self._db_path) as conn:
            conn.row_factory = aiosqlite.Row
            await self._ensure_tables(conn)
            async with conn.execute(
                "SELECT * FROM checkpoints WHERE checkpoint_id = ?", (checkpoint_id,)
            ) as cursor:
                row = await cursor.fetchone()
            if row is None:
                return None
            return Checkpoint(
                session_id=row["session_id"],
                checkpoint_id=row["checkpoint_id"],
                round_index=row["round_index"],
                state=EngineState[row["state"]],
                messages=_messages_from_json(row["messages"]),
                created_at=row["created_at"],
            )

    async def list_for_session(self, session_id: str) -> list[str]:
        async with aiosqlite.connect(self._db_path) as conn:
            conn.row_factory = aiosqlite.Row
            await self._ensure_tables(conn)
            async with conn.execute(
                "SELECT checkpoint_id FROM checkpoints WHERE session_id = ? ORDER BY created_at",
                (session_id,),
            ) as cursor:
                rows = await cursor.fetchall()
            return [row["checkpoint_id"] for row in rows]

    async def delete(self, checkpoint_id: str) -> None:
        async with aiosqlite.connect(self._db_path) as conn:
            await self._ensure_tables(conn)
            await conn.execute(
                "DELETE FROM checkpoints WHERE checkpoint_id = ?", (checkpoint_id,)
            )
            await conn.commit()
