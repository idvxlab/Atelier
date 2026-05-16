"""
spawn_agent / spawn_agents built-in tools.

spawn_agent  — create ONE sub-agent, run it to completion, return its response.
spawn_agents — create MULTIPLE sub-agents in parallel, return all responses.

Design notes:
  - Handler factories (make_*) accept runtime deps as closure args to avoid
    carrying them through the ToolRegistry (which stores plain async callables).
  - `from harness.factory import build_engine` is a lazy import inside the
    handler body to break the spawn_agent.py ↔ factory.py circular import.
  - MAX_SPAWN_DEPTH prevents infinite recursion: depth 0 = top-level agent,
    depth 3 = deepest allowed child. Exceeding returns an error string.
"""
from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING

from harness.types.tools import ToolSchema, ToolParam

if TYPE_CHECKING:
    from harness.config import HarnessConfig, ProviderConfig
    from harness.storage.session import SessionStore

MAX_SPAWN_DEPTH = 3

SPAWN_AGENT_SCHEMA = ToolSchema(
    name="spawn_agent",
    description=(
        "Create a sub-agent to handle a specific subtask. The sub-agent runs to "
        "completion and returns its final response. Use this to delegate a focused "
        "piece of work to a specialised agent with an optional custom system prompt "
        "and tool set."
    ),
    params=[
        ToolParam(
            name="task",
            type="string",
            description="The task or goal for the sub-agent.",
        ),
        ToolParam(
            name="system_prompt",
            type="string",
            description="Optional system prompt override for the sub-agent.",
            required=False,
        ),
        ToolParam(
            name="tools",
            type="array",
            description=(
                "Tool names to give the sub-agent. "
                "Omit to inherit the parent's global config."
            ),
            required=False,
            items={"type": "string"},
        ),
    ],
)

SPAWN_AGENTS_SCHEMA = ToolSchema(
    name="spawn_agents",
    description=(
        "Run multiple sub-agents in parallel. Each agent receives its own task and "
        "runs independently. All results are returned together once every agent "
        "finishes. Use this to parallelise independent subtasks."
    ),
    params=[
        ToolParam(
            name="agents",
            type="array",
            description=(
                "List of agent configurations. "
                "Each item: {task: str, system_prompt?: str, tools?: list[str]}"
            ),
            items={"type": "object"},
        ),
    ],
)


def make_spawn_agent_tool(
    harness_cfg: "HarnessConfig",
    provider_cfg: "ProviderConfig",
    session_store: "SessionStore",
    spawn_depth: int = 0,
):
    """Return a spawn_agent handler closed over the given runtime dependencies."""

    async def spawn_agent_tool(
        task: str,
        system_prompt: str = "",
        tools: list[str] | None = None,
    ) -> str:
        # Lazy import breaks the spawn_agent.py ↔ factory.py circular dependency
        from harness.factory import build_engine  # noqa: PLC0415

        if spawn_depth >= MAX_SPAWN_DEPTH:
            return (
                f"Error: maximum agent spawn depth ({MAX_SPAWN_DEPTH}) reached. "
                "Cannot create further sub-agents."
            )

        sub_id = f"sub_{uuid.uuid4().hex[:8]}"
        try:
            sub_engine = build_engine(
                session_id=sub_id,
                provider_cfg=provider_cfg,
                harness_cfg=harness_cfg,
                session_store=session_store,
                system_prompt=system_prompt,
                allowed_tools=tools,        # None → inherit global config
                spawn_depth=spawn_depth + 1,
            )
            return await sub_engine.run_to_completion(task)
        except Exception as exc:
            return f"Error: sub-agent '{sub_id}' failed — {exc}"

    return spawn_agent_tool


def make_spawn_agents_tool(
    harness_cfg: "HarnessConfig",
    provider_cfg: "ProviderConfig",
    session_store: "SessionStore",
    spawn_depth: int = 0,
):
    """Return a spawn_agents handler closed over the given runtime dependencies."""

    async def spawn_agents_tool(agents: list[dict]) -> str:
        from harness.factory import build_engine  # noqa: PLC0415

        if spawn_depth >= MAX_SPAWN_DEPTH:
            return (
                f"Error: maximum agent spawn depth ({MAX_SPAWN_DEPTH}) reached. "
                "Cannot create further sub-agents."
            )
        if not agents:
            return "Error: agents list is empty."

        async def run_one(cfg: dict) -> str:
            sub_id = f"sub_{uuid.uuid4().hex[:8]}"
            sub_engine = build_engine(
                session_id=sub_id,
                provider_cfg=provider_cfg,
                harness_cfg=harness_cfg,
                session_store=session_store,
                system_prompt=cfg.get("system_prompt", ""),
                allowed_tools=cfg.get("tools"),
                spawn_depth=spawn_depth + 1,
            )
            task = cfg.get("task", "")
            label = task[:60] + ("…" if len(task) > 60 else "")
            try:
                result = await sub_engine.run_to_completion(task)
                return f"[Sub-agent | {label}]\n{result}"
            except Exception as exc:
                return f"[Sub-agent | {label}]\nError: {exc}"

        results = await asyncio.gather(*[run_one(cfg) for cfg in agents])
        return "\n\n---\n\n".join(results)

    return spawn_agents_tool
