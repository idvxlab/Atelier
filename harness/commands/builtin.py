"""Built-in command definitions.

Two handler patterns (mirroring OpenCode):

- **Prompt commands** return ``CommandResult(kind="prompt")`` — the
  caller (CLI / REST) sends the text to the AI engine.
- **Internal commands** return ``CommandResult(kind="internal")`` —
  the caller executes the named action itself.
"""

from __future__ import annotations

from harness.commands.models import Command, CommandResult, CommandContext


def make_builtin_commands() -> list[Command]:
    return [
        Command(
            id="help",
            title="Help",
            description="Show all available commands",
            handler=_help_handler,
        ),
        Command(
            id="init",
            title="Initialize Project",
            description="Create/Update the MYHARNESS.md project memory file",
            handler=_init_handler,
        ),
        Command(
            id="compact",
            title="Compact Session",
            description="Summarize the current conversation to save context",
            handler=_compact_handler,
        ),
        Command(
            id="tools",
            title="List Tools",
            description="Show available tools and their descriptions",
            handler=_tools_handler,
        ),
        Command(
            id="skills",
            title="List Skills",
            description="Show available skills",
            handler=_skills_handler,
        ),
        Command(
            id="personas",
            title="List Personas",
            description="Show available personas",
            handler=_personas_handler,
        ),
        Command(
            id="state",
            title="Engine State",
            description="Show current engine state",
            handler=_state_handler,
        ),
        Command(
            id="exit",
            title="Exit",
            description="Exit the CLI",
            handler=_exit_handler,
        ),
        Command(
            id="skill-install",
            title="Install Skill",
            description="Install a skill from a local path or git URL into .myharness/skills/",
            handler=_skill_install_handler,
        ),
    ]


# ── Prompt commands ──────────────────────────────────────────────────────────


def _init_handler(cmd: Command, ctx: CommandContext) -> CommandResult:
    return CommandResult(
        kind="prompt",
        prompt_text=(
            "Please analyze this codebase and create or update a MYHARNESS.md file "
            "containing:\n\n"
            "1. Build/lint/test commands — especially for running a single test\n"
            "2. Code style guidelines including imports, formatting, types, "
            "naming conventions, error handling\n"
            "3. Project architecture overview\n\n"
            "If a MYHARNESS.md already exists, improve it."
        ),
    )


def _compact_handler(cmd: Command, ctx: CommandContext) -> CommandResult:
    return CommandResult(
        kind="prompt",
        prompt_text=(
            "Please write a concise summary of our conversation so far. "
            "Focus on:\n"
            "1. What the user asked for (the original task)\n"
            "2. What has been done so far (key actions and findings)\n"
            "3. What remains to be done (next steps)\n"
            "4. Important decisions or constraints discovered along the way\n\n"
            "Keep the summary dense and actionable — it will be used to "
            "continue the conversation in a fresh context window."
        ),
    )


# ── Internal commands ────────────────────────────────────────────────────────


def _help_handler(cmd: Command, ctx: CommandContext) -> CommandResult:
    return CommandResult(kind="internal", action="help")


def _tools_handler(cmd: Command, ctx: CommandContext) -> CommandResult:
    return CommandResult(kind="internal", action="list-tools")


def _skills_handler(cmd: Command, ctx: CommandContext) -> CommandResult:
    return CommandResult(kind="internal", action="list-skills")


def _personas_handler(cmd: Command, ctx: CommandContext) -> CommandResult:
    return CommandResult(kind="internal", action="list-personas")


def _state_handler(cmd: Command, ctx: CommandContext) -> CommandResult:
    return CommandResult(kind="internal", action="show-state")


def _exit_handler(cmd: Command, ctx: CommandContext) -> CommandResult:
    return CommandResult(kind="internal", action="exit")


def _skill_install_handler(cmd: Command, ctx: CommandContext) -> CommandResult:
    return CommandResult(
        kind="prompt",
        prompt_text=(
            "Install a skill from the provided source into .myharness/skills/.\n\n"
            "The source can be:\n"
            "- A local folder path: copy it to .myharness/skills/<skill-name>/\n"
            "- A git URL: clone it to .myharness/skills/<skill-name>/\n\n"
            "Steps:\n"
            "1. Determine the skill name from the source path/URL\n"
            "2. Create .myharness/skills/<name>/ if it doesn't exist\n"
            "3. Copy or clone the source into that directory\n"
            "4. Verify .myharness/skills/<name>/SKILL.md exists\n"
            "5. Confirm: 'Skill <name> installed. Use /skills to verify.'\n\n"
            "The skill will be available immediately in the next session."
        ),
    )
