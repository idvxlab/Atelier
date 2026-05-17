from __future__ import annotations

from harness.types.tools import ToolSchema, ToolParam

EDIT_FILE_SCHEMA = ToolSchema(
    name="edit_file",
    description="Precisely replace a section of text in a file. Raises an error if old_string appears multiple times unless replace_all is set.",
    params=[
        ToolParam(name="path", type="string", description="File to edit"),
        ToolParam(name="old_string", type="string", description="Exact text to find and replace"),
        ToolParam(name="new_string", type="string", description="Replacement text"),
        ToolParam(
            name="replace_all",
            type="boolean",
            description="Replace all occurrences of old_string (default: false — error if more than one match)",
            required=False,
        ),
    ],
)


async def edit_file_tool(
    path: str,
    old_string: str,
    new_string: str,
    replace_all: bool = False,
) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        return f"Error: file not found: {path}"
    except PermissionError:
        return f"Error: permission denied: {path}"
    except Exception as exc:
        return f"Error reading {path}: {exc}"

    count = content.count(old_string)

    if count == 0:
        return f"Error: old_string not found in {path}"
    if count > 1 and not replace_all:
        return f"Error: old_string appears {count} times in {path}. Set replace_all=true to replace all occurrences."

    if replace_all:
        new_content = content.replace(old_string, new_string)
    else:
        new_content = content.replace(old_string, new_string, 1)

    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)
    except PermissionError:
        return f"Error: permission denied: {path}"
    except Exception as exc:
        return f"Error writing to {path}: {exc}"

    replaced = "all" if replace_all else "first"
    return f"Replaced {replaced} occurrence(s) in {path}."
