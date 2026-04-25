from __future__ import annotations
from harness.types.tools import ToolSchema, ToolParam

READ_FILE_SCHEMA = ToolSchema(
    name="read_file",
    description="Read the contents of a file.",
    params=[
        ToolParam(name="path", type="string", description="Path to the file to read"),
        ToolParam(name="offset", type="integer", description="Line offset to start from (0-indexed)", required=False),
        ToolParam(name="limit", type="integer", description="Maximum number of lines to read", required=False),
    ],
)

async def read_file_tool(
    path: str,
    offset: int = 0,
    limit: int | None = None,
) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return f"Error: file not found: {path}"
    except PermissionError:
        return f"Error: permission denied: {path}"
    except Exception as exc:
        return f"Error reading {path}: {exc}"

    sliced = lines[offset:] if limit is None else lines[offset: offset + limit]
    return "".join(sliced)
