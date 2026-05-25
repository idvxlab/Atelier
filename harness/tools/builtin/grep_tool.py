from __future__ import annotations
import fnmatch
import re
from pathlib import Path
from harness.types.tools import ToolSchema, ToolParam

GREP_SCHEMA = ToolSchema(
    name="grep",
    description=(
        "Search file CONTENT by regex with optional surrounding context lines (like grep -C/-B/-A). "
        "Returns matching lines with file path and line number. "
        "Use this when you need context around matches, or want to filter by file extension (file_pattern). "
        "Prefer search for a simple no-context search; use glob to find files by name rather than content."
    ),
    params=[
        ToolParam(name="pattern", type="string", description="Regex or literal string to search for"),
        ToolParam(name="path", type="string", description="File or directory to search in"),
        ToolParam(name="context", type="integer", description="Show N lines before AND after each match (like grep -C)", required=False),
        ToolParam(name="before_context", type="integer", description="Show N lines before each match (like grep -B); overrides context", required=False),
        ToolParam(name="after_context", type="integer", description="Show N lines after each match (like grep -A); overrides context", required=False),
        ToolParam(name="case_sensitive", type="boolean", description="Case-sensitive search (default true)", required=False),
        ToolParam(name="file_pattern", type="string", description="Only search files whose name matches this pattern, e.g. *.py", required=False),
        ToolParam(name="max_results", type="integer", description="Maximum number of matching lines to return (default 50)", required=False),
    ],
)


async def grep_tool(
    pattern: str,
    path: str,
    context: int | None = None,
    before_context: int | None = None,
    after_context: int | None = None,
    case_sensitive: bool = True,
    file_pattern: str | None = None,
    max_results: int = 50,
) -> str:
    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        compiled = re.compile(pattern, flags)
    except re.error as exc:
        return f"Error: invalid regex pattern: {exc}"

    # before_context / after_context override the symmetric context shorthand
    n_before = before_context if before_context is not None else (context or 0)
    n_after  = after_context  if after_context  is not None else (context or 0)

    groups: list[list[str]] = []
    match_count = 0

    def _grep_file(filepath: str) -> None:
        nonlocal match_count
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except (PermissionError, IsADirectoryError):
            return

        match_indices = [i for i, ln in enumerate(lines) if compiled.search(ln)]
        if not match_indices:
            return

        # Build context windows and merge overlapping ones into single hunks
        hunks: list[tuple[int, int]] = []
        for idx in match_indices:
            start = max(0, idx - n_before)
            end   = min(len(lines), idx + n_after + 1)
            if hunks and start <= hunks[-1][1]:
                hunks[-1] = (hunks[-1][0], max(hunks[-1][1], end))
            else:
                hunks.append((start, end))

        for hunk_start, hunk_end in hunks:
            if match_count >= max_results:
                return
            group: list[str] = []
            for i in range(hunk_start, hunk_end):
                content = lines[i].rstrip()
                if compiled.search(lines[i]):
                    group.append(f"{filepath}:{i + 1}: {content}")
                    match_count += 1
                else:
                    group.append(f"{filepath}-{i + 1}- {content}")
            if group:
                groups.append(group)

    root = Path(path)
    if not root.exists():
        return f"Error: path not found: {path}"

    if root.is_file():
        _grep_file(str(root))
    elif root.is_dir():
        for file_path in sorted(root.rglob("*")):
            if match_count >= max_results:
                break
            if not file_path.is_file():
                continue
            if file_pattern and not fnmatch.fnmatch(file_path.name, file_pattern):
                continue
            _grep_file(str(file_path))
    else:
        return f"Error: path not found: {path}"

    if not groups:
        return f"No matches found for pattern {pattern!r} in {path}"

    output = "\n--\n".join("\n".join(group) for group in groups)
    if match_count >= max_results:
        output += f"\n[Truncated at {max_results} results]"
    return output
