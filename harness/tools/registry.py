from __future__ import annotations
from dataclasses import dataclass
from harness.types.tools import ToolSchema, ToolHandler

@dataclass
class RegisteredTool:
    schema: ToolSchema
    handler: ToolHandler

class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}

    def register(self, schema: ToolSchema, handler: ToolHandler) -> None:
        self._tools[schema.name] = RegisteredTool(schema=schema, handler=handler)

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def discover(self) -> list[RegisteredTool]:
        """Return fresh list every call — NEVER cache the result."""
        return list(self._tools.values())

    def get(self, name: str) -> RegisteredTool | None:
        return self._tools.get(name)

    def schemas(self) -> list[ToolSchema]:
        return [t.schema for t in self._tools.values()]
