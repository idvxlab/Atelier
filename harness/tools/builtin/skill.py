"""
use_skill built-in tool.

Allows the agent to load a skill's instructions on demand.
The agent discovers available skills from the system prompt (names + descriptions),
then calls this tool to fetch the full instructions when a task matches.
"""
from __future__ import annotations

from harness.skills import load_skill, list_skills
from harness.types.tools import ToolSchema, ToolParam
from pathlib import Path

USE_SKILL_SCHEMA = ToolSchema(
    name="use_skill",
    description=(
        "Load a predefined skill and return its detailed instructions. "
        "Call this when the user's request matches a skill's description. "
        "Follow the returned instructions to complete the task."
    ),
    params=[
        ToolParam(
            name="name",
            type="string",
            description="The skill name to load (e.g. 'code-review', 'python-dev')",
        ),
        ToolParam(
            name="arguments",
            type="string",
            required=False,
            description="Optional arguments to pass to the skill (e.g. file path, search query)",
        ),
    ],
)


async def use_skill_tool(name: str, arguments: str = "") -> str:
    try:
        meta = load_skill(name)
        content = meta.get("system_prompt", "")
        if not content:
            return f"Skill '{name}' exists but has no instructions."

        source = meta.get("_source_file", "")
        base_dir = str(Path(source).parent) if source else f"skills/{name}"

        result = (
            f"Base directory: {base_dir}\n\n"
            f"# Skill: {name}\n\n"
            f"{content}"
        )

        if arguments:
            result += f"\n\n---\nArguments: {arguments}"

        result += f"\n\n---\nFollow the above instructions for the current task."
        return result
    except ValueError:
        available = [s["name"] for s in list_skills()]
        return (
            f"Skill '{name}' not found. "
            f"Available: {', '.join(available) or 'none'}"
        )
