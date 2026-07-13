from __future__ import annotations

from pathlib import Path

from harness.types.tools import ToolParam, ToolSchema


LIST_DIR_SCHEMA = ToolSchema(
    name="list_dir",
    description="List files and directories under a path.",
    params=[
        ToolParam(name="path", type="string", description="Directory path to list"),
        ToolParam(
            name="recursive",
            type="boolean",
            description="List recursively instead of only direct children",
            required=False,
        ),
        ToolParam(
            name="max_results",
            type="integer",
            description="Maximum number of entries to return",
            required=False,
        ),
    ],
)


async def list_dir_tool(
    path: str = ".",
    recursive: bool = False,
    max_results: int = 200,
) -> str:
    try:
        root = Path(path)
        if not root.exists():
            return f"Error: directory not found: {path}"
        if not root.is_dir():
            return f"Error: not a directory: {path}"

        iterator = root.rglob("*") if recursive else root.iterdir()
        entries: list[str] = []
        limit = max(1, int(max_results or 200))
        for item in sorted(iterator, key=lambda p: str(p).casefold()):
            rel = item.relative_to(root)
            label = str(rel).replace("\\", "/")
            if item.is_dir():
                label += "/"
            entries.append(label)
            if len(entries) >= limit:
                break

        if not entries:
            return f"No entries in {path}."
        suffix = ""
        if len(entries) >= limit:
            suffix = f"\n... truncated at {limit} entries"
        return "\n".join(entries) + suffix
    except PermissionError:
        return f"Error: permission denied: {path}"
    except Exception as exc:
        return f"Error listing directory {path}: {exc}"
