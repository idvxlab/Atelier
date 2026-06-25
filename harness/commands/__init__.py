"""Command system for MyHarnessPy.

Provides a unified slash-command mechanism for both CLI and Web UI.
Built-in commands and file-based custom commands share the same registry
and dispatch logic.

Usage::

    cmd_system = CommandSystem()
    cmd_system.initialize()

    # Resolve "/help" or "/project:review"
    cmd = cmd_system.resolve("help")

    # List all commands for API / command palette
    for entry in cmd_system.list_all():
        print(entry["id"], entry["title"])
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from harness.commands.models import (
    Command,
    CommandResult,
    CommandContext,
    serialize_command,
)
from harness.commands.registry import CommandRegistry
from harness.commands.builtin import make_builtin_commands
from harness.commands.loader import load_custom_commands


class CommandSystem:
    """Top-level facade: owns the registry and orchestrates loading."""

    def __init__(
        self,
        project_dir: Path | None = None,
        user_dir: Path | None = None,
    ) -> None:
        self._registry = CommandRegistry()
        self._project_dir = project_dir or Path.cwd()
        self._user_dir = user_dir if user_dir is not None else Path.home() / ".myharness"
        self._initialized = False

    def initialize(self) -> None:
        """Register builtins then load custom commands. Idempotent."""
        if self._initialized:
            return
        for cmd in make_builtin_commands():
            self._registry.register(cmd)
        for cmd in load_custom_commands(self._project_dir, self._user_dir):
            self._registry.register(cmd)
        self._initialized = True

    def resolve(self, name: str) -> Command | None:
        """Resolve a command by full id or short name."""
        return self._registry.resolve(name)

    def discover(self) -> list[Command]:
        """Return all registered Command objects."""
        return self._registry.discover()

    def list_all(self) -> list[dict[str, Any]]:
        """Return all commands as JSON-safe dicts (for API / CLI)."""
        return [serialize_command(c) for c in self._registry.discover()]
