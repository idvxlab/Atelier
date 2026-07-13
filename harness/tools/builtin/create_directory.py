from __future__ import annotations

from pathlib import Path

from harness.types.tools import ToolParam, ToolSchema


CREATE_DIRECTORY_SCHEMA = ToolSchema(
    name="create_directory",
    description="Create a directory, including missing parent directories.",
    params=[
        ToolParam(name="path", type="string", description="Directory path to create"),
    ],
)


async def create_directory_tool(path: str) -> str:
    try:
        target = Path(path)
        existed = target.exists()
        if existed and not target.is_dir():
            return f"Error: path exists but is not a directory: {path}"
        target.mkdir(parents=True, exist_ok=True)
        if existed:
            return f"Directory already exists: {path}"
        return f"Created directory: {path}"
    except PermissionError:
        return f"Error: permission denied: {path}"
    except Exception as exc:
        return f"Error creating directory {path}: {exc}"
