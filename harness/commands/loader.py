"""Custom command loader — scans .md files and registers them as commands.

Mirrors OpenCode's ``LoadCustomCommands()``:
  - Project-level: ``.myharness/commands/`` → id prefix ``"project:"``
  - User-level (future): ``~/.myharness/commands/`` → id prefix ``"user:"``

File path to command ID mapping::

    .myharness/commands/deploy.md          → project:deploy
    .myharness/commands/github/issue.md    → project:github:issue
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from harness.commands.models import (
    Command,
    CommandResult,
    CommandContext,
    PARAM_PATTERN,
    extract_params,
)


def _make_custom_handler(content: str):
    """Return a handler for a markdown-based custom command.

    If *content* contains ``$UPPER_VAR`` placeholders the handler returns
    ``kind="needs-args"`` so the caller prompts the user; otherwise it
    returns ``kind="prompt"`` directly.
    """

    def handler(cmd: Command, ctx: CommandContext) -> CommandResult:
        params = extract_params(content)
        if params:
            return CommandResult(
                kind="needs-args",
                args_needed=params,
                raw_content=content,
                command_id=cmd.id,
            )
        return CommandResult(kind="prompt", prompt_text=content)

    return handler


def _parse_command_file(path: Path, default_id: str) -> Command | None:
    """Parse a .md file with optional YAML frontmatter into a Command.

    Frontmatter fields: ``name``, ``title``, ``description``.
    Body: prompt template with optional ``$VAR`` placeholders.

    ``name`` overrides *default_id* when set.
    """
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", text, re.DOTALL)

    if m:
        try:
            meta: dict[str, Any] = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError:
            meta = {}
        body = m.group(2).strip()
    else:
        meta = {}
        body = text.strip()

    cmd_id = str(meta.get("name", default_id))
    title = str(
        meta.get(
            "title",
            cmd_id.rsplit(":", 1)[-1].replace("-", " ").title(),
        )
    )
    description = str(meta.get("description", ""))

    content = body
    params = extract_params(content)

    return Command(
        id=cmd_id,
        title=title,
        description=description,
        source="project",  # project-level default; caller may override
        handler=_make_custom_handler(content),
        raw_content=content,
        source_path=str(path),
        params=params,
    )


def _load_from_dir(
    directory: Path,
    prefix: str,
    source: str = "project",
) -> list[Command]:
    """Recursively walk *directory*, create a Command for each .md file.

    Args:
        directory: Root dir to scan.
        prefix:    ID prefix, e.g. ``"project"`` → ``"project:github:issue"``.
        source:    Value stored in ``Command.source``.
    """
    if not directory.is_dir():
        return []

    commands: list[Command] = []
    for md_file in sorted(directory.rglob("*.md")):
        rel = md_file.relative_to(directory)
        # Normalize Windows backslashes → forward slashes → colons
        segments = str(rel.with_suffix("")).replace("\\", "/").replace("/", ":")
        cmd_id = f"{prefix}:{segments}" if prefix else segments
        cmd = _parse_command_file(md_file, cmd_id)
        if cmd:
            cmd.source = source
            commands.append(cmd)
    return commands


def load_custom_commands(
    project_dir: Path | None = None,
    user_dir: Path | None = None,
) -> list[Command]:
    """Load custom commands from filesystem directories.

    Args:
        project_dir: Project root containing ``.myharness/commands/`` subdirectory.
        user_dir:    User-global commands directory (future).
    """
    all_cmds: list[Command] = []

    # Project-level
    pdir = (project_dir or Path.cwd()) / ".myharness" / "commands"
    all_cmds.extend(_load_from_dir(pdir, prefix="project", source="project"))

    # User-level (future)
    if user_dir:
        all_cmds.extend(_load_from_dir(user_dir, prefix="user", source="user"))

    return all_cmds
