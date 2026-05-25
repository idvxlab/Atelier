from __future__ import annotations
import re
from harness.types.tools import ToolSchema, ToolParam

SEARCH_SCHEMA = ToolSchema(
    name="search",
    description=(
        "Quick regex/literal search across file content — returns matching lines with file:line. "
        "Use this for a simple one-shot search when you don't need surrounding context lines. "
        "Prefer grep when you need context lines (before/after the match) or file-type filtering."
    ),
    params=[
        ToolParam(name="pattern", type="string", description="Regex or literal string to search for"),
        ToolParam(name="path", type="string", description="File or directory to search in"),
        ToolParam(name="case_sensitive", type="boolean", description="Case-sensitive search (default true)", required=False),
        ToolParam(name="max_results", type="integer", description="Maximum number of matching lines to return (default 100)", required=False),
    ],
)

async def search_tool(
    pattern: str,
    path: str,
    case_sensitive: bool = True,
    max_results: int = 100,
) -> str:
    import os
    flags = 0 if case_sensitive else re.IGNORECASE

    try:
        compiled = re.compile(pattern, flags)
    except re.error as exc:
        return f"Error: invalid regex pattern: {exc}"

    results: list[str] = []

    def search_file(filepath: str) -> None:
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                for lineno, line in enumerate(f, 1):
                    if compiled.search(line):
                        results.append(f"{filepath}:{lineno}: {line.rstrip()}")
                        if len(results) >= max_results:
                            return
        except (PermissionError, IsADirectoryError, UnicodeDecodeError):
            pass

    if os.path.isfile(path):
        search_file(path)
    elif os.path.isdir(path):
        for root, _, files in os.walk(path):
            for fname in files:
                if len(results) >= max_results:
                    break
                search_file(os.path.join(root, fname))
    else:
        return f"Error: path not found: {path}"

    if not results:
        return f"No matches found for pattern {pattern!r} in {path}"

    output = "\n".join(results)
    if len(results) >= max_results:
        output += f"\n[Truncated at {max_results} results]"
    return output
