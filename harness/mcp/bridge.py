"""Bridge between MCP Servers and the harness ToolRegistry.

Call ``register_mcp_server()`` after connecting an MCPClient to inject all
remote tools as native harness tools.  Each tool is wrapped in a closure
that delegates execution back to the MCPClient.
"""
from __future__ import annotations

import logging
from typing import Any

from harness.mcp.client import MCPClient
from harness.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


async def register_mcp_server(
    registry: ToolRegistry,
    client: MCPClient,
    prefix: str = "",
) -> list[str]:
    """Fetch all tools from *client* and register them into *registry*.

    Tool names are optionally namespaced with *prefix* + "__" to avoid
    collisions when multiple MCP Servers provide similarly named tools.
    E.g. ``prefix="filesystem"`` → ``"filesystem__read_file"``.

    Args:
        registry: The ToolRegistry to register tools into.
        client:   A connected MCPClient instance.
        prefix:   Optional namespace prefix (e.g. the server's config key).
                  Leave empty to use the bare tool name.

    Returns:
        Sorted list of the tool names that were registered.
    """
    schemas = await client.list_tools()
    registered: list[str] = []

    for schema in schemas:
        tool_name = f"{prefix}__{schema.name}" if prefix else schema.name

        # Re-create schema with (possibly) prefixed name so the LLM sees it
        from harness.types.tools import ToolSchema as _TS
        namespaced_schema = _TS(
            name=tool_name,
            description=schema.description,
            params=schema.params,
        )

        # Capture current values in the closure
        _client = client
        _remote_name = schema.name

        def _make_handler(mcp_client: MCPClient, remote_name: str):
            async def _handler(**kwargs: Any) -> str:
                return await mcp_client.call_tool(remote_name, kwargs)
            _handler.__name__ = remote_name
            return _handler

        handler = _make_handler(_client, _remote_name)
        registry.register(namespaced_schema, handler)
        registered.append(tool_name)
        logger.debug("Registered MCP tool: %s (→ %s)", tool_name, _remote_name)

    logger.info(
        "MCP bridge: registered %d tool(s) from server '%s': %s",
        len(registered),
        prefix or "<default>",
        registered,
    )
    return sorted(registered)
