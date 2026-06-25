"""Core data models for the command system."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Literal

if TYPE_CHECKING:
    from harness.engine.engine import AgentEngine
    from harness.config import HarnessConfig

# Parameter placeholder: $UPPER_VAR_NAME (OpenCode-compatible)
PARAM_PATTERN = re.compile(r"\$([A-Z][A-Z0-9_]*)")

# Source tag for commands
CommandSource = Literal["builtin", "project", "user"]

# Result kind
ResultKind = Literal["prompt", "internal", "needs-args", "error", "none"]


@dataclass
class Command:
    """A single command registered in the system.

    Built-in commands have a *handler* callable.
    Custom commands loaded from .md files have *raw_content* and an
    auto-generated handler that returns ``kind="prompt"`` or
    ``kind="needs-args"`` depending on whether ``$PARAM`` placeholders
    are present.
    """

    id: str
    title: str
    description: str = ""
    source: CommandSource = "builtin"
    handler: Callable[[Command, "CommandContext"], "CommandResult"] | None = None
    raw_content: str = ""       # original .md body (custom commands)
    source_path: str = ""       # file path (custom commands)
    params: list[str] = field(default_factory=list)  # deduced $VAR names


@dataclass
class CommandResult:
    """Returned by a command's handler to describe what should happen next."""

    kind: ResultKind = "none"
    prompt_text: str = ""       # for kind="prompt"
    action: str = ""            # for kind="internal"
    message: str = ""           # display message
    args_needed: list[str] = field(default_factory=list)  # for kind="needs-args"
    raw_content: str = ""       # un-substituted template
    command_id: str = ""


@dataclass
class CommandContext:
    """Injectable dependencies for command handlers.

    Created at startup (CLI or API) and passed to every handler so
    internal commands can query engine state, list tools, etc.
    """

    engine: AgentEngine | None = None
    config: HarnessConfig | None = None
    session_id: str = ""
    system_prompt: str = ""
    allowed_tools: list[str] | None = None
    provider_name: str = ""


def substitute_args(content: str, args: dict[str, str]) -> str:
    """Replace every ``$VAR`` placeholder in *content* with *args* values."""
    result = content
    for name, value in args.items():
        result = result.replace(f"${name}", value)
    return result


def extract_params(content: str) -> list[str]:
    """Return deduplicated, order-preserving list of $VAR names in *content*."""
    seen: set[str] = set()
    result: list[str] = []
    for m in PARAM_PATTERN.finditer(content):
        name = m.group(1)
        if name not in seen:
            seen.add(name)
            result.append(name)
    return result


def serialize_command(cmd: Command) -> dict[str, Any]:
    """Convert a Command to a JSON-safe dict for API responses."""
    return {
        "id": cmd.id,
        "title": cmd.title,
        "description": cmd.description,
        "source": cmd.source,
        "has_params": bool(cmd.params),
        "params": cmd.params,
    }
