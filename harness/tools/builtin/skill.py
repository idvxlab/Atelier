"""
use_skill built-in tool.

Allows the agent to load any Skill's instructions on demand.
The agent discovers available Skills from names and descriptions, without
requiring a category, then fetches full instructions when relevant.
"""
from __future__ import annotations

import json

from harness.skills import load_skill, list_skills as discover_skills
from harness.types.tools import ToolSchema, ToolParam
from pathlib import Path

USE_SKILL_SCHEMA = ToolSchema(
    name="use_skill",
    description=(
        "Load any installed Skill by name and return its full instructions. "
        "Skills are unclassified and may provide knowledge, methods, rubrics, "
        "protocols, or workflows. Use the description and user intent to decide "
        "when to load one."
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

LIST_SKILLS_SCHEMA = ToolSchema(
    name="list_skills",
    description=(
        "Refresh and list installed Skills by name, description, and source. "
        "Skills are unclassified. Use this when the user mentions a newly "
        "installed Skill or when you need to discover relevant instructions "
        "before calling use_skill."
    ),
    params=[
        ToolParam(
            name="query",
            type="string",
            required=False,
            description="Optional text filter matched against Skill names and descriptions.",
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
        available = [s["name"] for s in discover_skills()]
        return (
            f"Skill '{name}' not found. "
            f"Available: {', '.join(available) or 'none'}"
        )


async def list_skills_tool(query: str = "") -> str:
    skills = discover_skills()
    needle = query.strip().casefold()
    if needle:
        skills = [
            skill
            for skill in skills
            if needle in str(skill.get("name", "")).casefold()
            or needle in str(skill.get("description", "")).casefold()
        ]
    return json.dumps(
        {
            "ok": True,
            "query": query,
            "count": len(skills),
            "skills": skills,
        },
        ensure_ascii=False,
        indent=2,
    )
