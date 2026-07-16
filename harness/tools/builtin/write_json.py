from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from harness.types.tools import ToolSchema, ToolParam


WRITE_JSON_SCHEMA = ToolSchema(
    name="write_json",
    description=(
        "Write structured JSON data to a file, creating parent directories if "
        "needed. Prefer this over write_file for JSON files because the data is "
        "passed as an object, not as an escaped JSON string."
    ),
    params=[
        ToolParam(name="path", type="string", description="Destination .json file path"),
        ToolParam(name="data", type="object", description="JSON object to write"),
        ToolParam(
            name="indent",
            type="integer",
            description="JSON indentation spaces, default 2",
            required=False,
        ),
    ],
)


async def write_json_tool(path: str, data: Any, indent: int = 2) -> str:
    try:
        parent = Path(path).parent
        if parent and not parent.exists():
            os.makedirs(parent, exist_ok=True)

        text = json.dumps(data, ensure_ascii=False, indent=indent)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
            f.write("\n")

        return f"Written JSON object with {len(text)} character(s) to {path}."
    except TypeError as exc:
        return f"Error: data is not JSON serializable: {exc}"
    except PermissionError:
        return f"Error: permission denied: {path}"
    except Exception as exc:
        return f"Error writing JSON to {path}: {exc}"
