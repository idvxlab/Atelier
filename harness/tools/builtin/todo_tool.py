from __future__ import annotations

from harness.types.tools import ToolSchema, ToolParam

TODO_WRITE_SCHEMA = ToolSchema(
    name="todo_write",
    description="Manage a session-level task todo list stored in memory.",
    params=[
        ToolParam(name="session_id", type="string", description="Current session identifier"),
        ToolParam(
            name="action",
            type="string",
            description="Action: set (initialize list), update (change status), or get (retrieve list)",
        ),
        ToolParam(
            name="todos",
            type="array",
            description="List of todo items with 'content' and 'status' fields (use with action=set)",
            required=False,
        ),
        ToolParam(
            name="index",
            type="integer",
            description="Zero-based index of the todo item to update (use with action=update)",
            required=False,
        ),
        ToolParam(
            name="status",
            type="string",
            description="New status: pending, in_progress, or completed (use with action=update)",
            required=False,
        ),
    ],
)

# In-memory session-level todo store: session_id -> list of dicts
_TODO_STORE: dict[str, list[dict]] = {}


async def todo_write_tool(
    session_id: str,
    action: str,
    todos: list[dict] | None = None,
    index: int | None = None,
    status: str | None = None,
) -> str:
    global _TODO_STORE

    if action == "set":
        if todos is None:
            return "Error: todos is required when action=set"
        _TODO_STORE[session_id] = list(todos)
        return f"Todo list set with {len(todos)} item(s)."

    if action == "get":
        items = _TODO_STORE.get(session_id, [])
        if not items:
            return "No todo items."
        lines = []
        for i, item in enumerate(items):
            lines.append(f"[{i}] [{item.get('status', 'pending')}] {item.get('content', '')}")
        return "\n".join(lines)

    if action == "update":
        if index is None:
            return "Error: index is required when action=update"
        items = _TODO_STORE.get(session_id, [])
        if not items:
            return f"Error: no todo items found for session {session_id}"
        if index < 0 or index >= len(items):
            return f"Error: index {index} out of range (0-{len(items) - 1})"
        if status not in ("pending", "in_progress", "completed"):
            return f"Error: status must be one of pending, in_progress, completed; got '{status}'"
        items[index]["status"] = status
        return f"Updated item [{index}] → {status}."

    return f"Error: unknown action '{action}'. Use set, update, or get."
