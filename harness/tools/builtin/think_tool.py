from __future__ import annotations

from harness.types.tools import ToolSchema, ToolParam

THINK_SCHEMA = ToolSchema(
    name="think",
    description="Output a reasoning thought before taking action. The tool itself does nothing — it simply echoes the thought content back so the agent can articulate its reasoning process.",
    params=[
        ToolParam(
            name="thought",
            type="string",
            description="The agent's reasoning or thought process to articulate",
        ),
    ],
)


async def think_tool(thought: str) -> str:
    return thought
