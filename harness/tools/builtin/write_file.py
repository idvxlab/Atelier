from __future__ import annotations
import os
from pathlib import Path

from harness.types.tools import ToolSchema, ToolParam

WRITE_FILE_SCHEMA = ToolSchema(
    name="write_file",
    description=(
        "Write plain text files such as Markdown, HTML, CSS, or source code, "
        "creating parent directories if needed. For .json files, use write_json "
        "instead so the model passes structured data instead of a long escaped string."
    ),
    params=[
        ToolParam(name="path", type="string", description="Destination file path"),
        ToolParam(name="content", type="string", description="Content to write"),
        ToolParam(
            name="append",
            type="boolean",
            description="Append to existing file instead of overwriting (default: false)",
            required=False,
        ),
    ],
)


async def write_file_tool(path: str, content: str, append: bool = False) -> str:
    try:
        # Auto-create parent directories
        parent = Path(path).parent
        if parent and not parent.exists():
            os.makedirs(parent, exist_ok=True)

        mode = "a" if append else "w"
        with open(path, mode, encoding="utf-8") as f:
            f.write(content)

        action = "Appended" if append else "Written"
        return f"{action} {len(content)} character(s) to {path}."
    except PermissionError:
        return f"Error: permission denied: {path}"
    except Exception as exc:
        return f"Error writing to {path}: {exc}"
