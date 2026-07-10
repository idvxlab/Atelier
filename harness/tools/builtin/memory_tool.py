from __future__ import annotations

import json
from dataclasses import asdict
from typing import TYPE_CHECKING

from harness.types.tools import ToolParam, ToolSchema

if TYPE_CHECKING:
    from harness.storage.memory_store import MemoryStore


MEMORY_SCHEMA = ToolSchema(
    name="memory",
    description=(
        "Store and retrieve durable long-term memories across sessions. "
        "Use only for stable user/project preferences, decisions, facts, or "
        "lessons that are likely to be useful later."
    ),
    params=[
        ToolParam(
            name="action",
            type="string",
            description="Action: add, search, list, get, or delete.",
        ),
        ToolParam(
            name="content",
            type="string",
            description="Memory text to store when action=add.",
            required=False,
        ),
        ToolParam(
            name="query",
            type="string",
            description="Text query for action=search.",
            required=False,
        ),
        ToolParam(
            name="entry_id",
            type="string",
            description="Memory id for action=get or action=delete.",
            required=False,
        ),
        ToolParam(
            name="scope",
            type="string",
            description="Optional memory scope, defaults to global.",
            required=False,
        ),
        ToolParam(
            name="tags",
            type="array",
            description="Optional tags for adding or filtering memories.",
            required=False,
            items={"type": "string"},
        ),
        ToolParam(
            name="session_id",
            type="string",
            description="Current session id, recorded on new memories.",
            required=False,
        ),
        ToolParam(
            name="limit",
            type="integer",
            description="Maximum number of memories to return for search/list.",
            required=False,
        ),
    ],
)


def _normalise_tags(tags: list[str] | None) -> list[str]:
    cleaned: list[str] = []
    for tag in tags or []:
        value = str(tag).strip()
        if value and value not in cleaned:
            cleaned.append(value)
    return cleaned


def _render_entries(entries: list) -> str:
    if not entries:
        return "No memories found."
    return json.dumps([asdict(entry) for entry in entries], ensure_ascii=False, indent=2)


def make_memory_tool(memory_store: "MemoryStore"):
    async def memory_tool(
        action: str,
        content: str = "",
        query: str = "",
        entry_id: str = "",
        scope: str = "global",
        tags: list[str] | None = None,
        session_id: str = "",
        limit: int = 20,
    ) -> str:
        action = (action or "").strip().lower()
        scope = (scope or "global").strip() or "global"
        clean_tags = _normalise_tags(tags)

        if action == "add":
            text = (content or "").strip()
            if not text:
                return "Error: content is required when action=add"
            entry = await memory_store.add(
                content=text,
                scope=scope,
                tags=clean_tags,
                created_by_session=session_id,
            )
            return json.dumps(asdict(entry), ensure_ascii=False, indent=2)

        if action == "search":
            entries = await memory_store.search(
                query=(query or "").strip(),
                scope="" if scope == "global" and not query and not clean_tags else scope,
                tags=clean_tags,
                limit=limit,
            )
            return _render_entries(entries)

        if action == "list":
            entries = await memory_store.search(
                query="",
                scope=scope,
                tags=clean_tags,
                limit=limit,
            )
            return _render_entries(entries)

        if action == "get":
            if not entry_id:
                return "Error: entry_id is required when action=get"
            entry = await memory_store.get(entry_id)
            if entry is None:
                return f"Error: memory entry '{entry_id}' not found"
            return json.dumps(asdict(entry), ensure_ascii=False, indent=2)

        if action == "delete":
            if not entry_id:
                return "Error: entry_id is required when action=delete"
            deleted = await memory_store.delete(entry_id)
            return "Deleted." if deleted else f"Error: memory entry '{entry_id}' not found"

        return "Error: unknown action. Use add, search, list, get, or delete."

    return memory_tool
