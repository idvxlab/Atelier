"""CommandRegistry — register, discover, resolve commands.

Follows the same register/discover/get pattern as
``harness.tools.registry.ToolRegistry``.
"""

from __future__ import annotations

from harness.commands.models import Command


class CommandRegistry:
    """In-memory store for built-in and custom commands."""

    def __init__(self) -> None:
        self._commands: dict[str, Command] = {}

    def register(self, cmd: Command) -> None:
        """Add or overwrite a command by its id."""
        self._commands[cmd.id] = cmd

    def unregister(self, cmd_id: str) -> None:
        self._commands.pop(cmd_id, None)

    def discover(self) -> list[Command]:
        """Return all registered commands (no particular order)."""
        return list(self._commands.values())

    def get(self, cmd_id: str) -> Command | None:
        """Exact match by full id."""
        return self._commands.get(cmd_id)

    def resolve(self, name: str) -> Command | None:
        """Resolve by exact id first, then by short-name fallback.

        Short-name matching uses the final colon-separated segment, e.g.
        ``"issue"`` matches ``"project:github:issue"``.  When multiple
        commands share the same short name, the first registered wins
        (built-in commands are registered first).
        """
        if name in self._commands:
            return self._commands[name]
        for cmd in self._commands.values():
            if cmd.id.rsplit(":", 1)[-1] == name:
                return cmd
        return None
