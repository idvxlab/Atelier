from __future__ import annotations
from pathlib import Path
from harness.types.tools import ToolSchema, ToolParam

GLOB_SCHEMA = ToolSchema(
    name="glob",
    description="Find files by name pattern using pathlib glob. Returns matching file paths.",
    params=[
        ToolParam(name="pattern", type="string", description="Glob pattern to match, e.g. **/*.py"),
        ToolParam(name="path", type="string", description="Root directory to search in (default '.')", required=False),
        ToolParam(name="max_results", type="integer", description="Maximum number of results to return (default 100)", required=False),
    ],
)


async def glob_tool(
    pattern: str,
    path: str = ".",
    max_results: int = 100,
) -> str:
    root = Path(path)
    if not root.exists():
        return f"Error: path not found: {path}"
    if not root.is_dir():
        return f"Error: path is not a directory: {path}"

    try:
        matches: list[Path] = []
        for match in root.glob(pattern):
            if not match.is_file():
                continue
            matches.append(match)
            if len(matches) >= max_results:
                break
    except ValueError as exc:
        return f"Error: invalid glob pattern: {exc}"

    if not matches:
        return f"No files found matching pattern {pattern!r} in {path}"

    lines = [str(p.as_posix()) for p in sorted(matches)]
    output = "\n".join(lines)
    if len(matches) >= max_results:
        output += f"\n[Truncated at {max_results} results]"
    return output
