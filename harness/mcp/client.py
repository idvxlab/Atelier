"""High-level MCP client.

Wraps StdioTransport and speaks the MCP JSON-RPC protocol:
  • initialize / initialized handshake
  • tools/list
  • tools/call
"""
from __future__ import annotations

import json
import logging
from typing import Any

from harness.mcp.stdio_transport import StdioTransport, TransportError
from harness.types.tools import ToolSchema, ToolParam

logger = logging.getLogger(__name__)

# MCP protocol version we advertise during the handshake.
_PROTOCOL_VERSION = "2024-11-05"


class MCPError(Exception):
    """Raised when the MCP Server returns a JSON-RPC error."""

    def __init__(self, code: int, message: str, data: Any = None) -> None:
        super().__init__(f"MCP error {code}: {message}")
        self.code = code
        self.data = data


class MCPClient:
    """Clean interface over the MCP stdio transport.

    Usage::

        client = MCPClient()
        await client.connect(["npx", "-y", "@modelcontextprotocol/server-filesystem", "."])
        tools = await client.list_tools()
        result = await client.call_tool("read_file", {"path": "README.md"})
        await client.close()
    """

    def __init__(self, server_name: str = "mcp-server") -> None:
        self._transport = StdioTransport()
        self._server_name = server_name
        self._connected = False

    # ── Lifecycle ────────────────────────────────────────────────────────────

    async def connect(self, command: list[str]) -> None:
        """Start the MCP Server and perform the initialize handshake.

        Args:
            command: Command + args used to launch the server process.
        """
        await self._transport.start(command)

        # Step 1 — send initialize
        init_response = await self._rpc(
            "initialize",
            {
                "protocolVersion": _PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "clientInfo": {"name": "MyHarnessPy", "version": "0.1.0"},
            },
        )
        logger.debug(
            "MCP initialize response from %s: %s", self._server_name, init_response
        )

        # Step 2 — send initialized notification (no response expected)
        await self._notify("notifications/initialized", {})

        self._connected = True
        logger.info("Connected to MCP Server '%s'.", self._server_name)

    async def close(self) -> None:
        """Gracefully shut down the connection."""
        self._connected = False
        await self._transport.close()
        logger.info("Disconnected from MCP Server '%s'.", self._server_name)

    # ── Tool discovery ────────────────────────────────────────────────────────

    async def list_tools(self) -> list[ToolSchema]:
        """Fetch the tool list from the MCP Server and convert to ToolSchema.

        Returns:
            List of ToolSchema objects compatible with harness ToolRegistry.
        """
        self._ensure_connected()
        result = await self._rpc("tools/list", {})
        raw_tools: list[dict] = result.get("tools", [])
        return [self._parse_tool(t) for t in raw_tools]

    # ── Tool invocation ───────────────────────────────────────────────────────

    async def call_tool(self, name: str, args: dict[str, Any]) -> str:
        """Invoke a tool on the MCP Server.

        Args:
            name: Tool name as returned by ``list_tools()``.
            args: Keyword arguments matching the tool's input schema.

        Returns:
            The tool output as a plain string (content blocks are joined).

        Raises:
            MCPError: If the server returns a JSON-RPC or tool-level error.
        """
        self._ensure_connected()
        result = await self._rpc("tools/call", {"name": name, "arguments": args})

        # MCP tools/call returns { content: [...], isError?: bool }
        if result.get("isError"):
            raw = self._extract_text(result.get("content", []))
            raise MCPError(-1, f"Tool '{name}' returned an error: {raw}")

        return self._extract_text(result.get("content", []))

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _ensure_connected(self) -> None:
        if not self._connected:
            raise TransportError(
                f"MCPClient '{self._server_name}' is not connected. "
                "Call connect() first."
            )

    async def _rpc(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Send a JSON-RPC request and return the ``result`` field."""
        rid = self._transport.next_id()
        msg = {
            "jsonrpc": "2.0",
            "id": rid,
            "method": method,
            "params": params,
        }
        response = await self._transport.send(msg)

        if "error" in response:
            err = response["error"]
            raise MCPError(
                code=err.get("code", -1),
                message=err.get("message", "unknown error"),
                data=err.get("data"),
            )

        return response.get("result", {})

    async def _notify(self, method: str, params: dict[str, Any]) -> None:
        """Send a JSON-RPC notification (no id, no response expected)."""
        assert self._transport._process and self._transport._process.stdin
        msg = {"jsonrpc": "2.0", "method": method, "params": params}
        line = json.dumps(msg, ensure_ascii=False) + "\n"
        self._transport._process.stdin.write(line.encode())
        await self._transport._process.stdin.drain()
        logger.debug("MCP notification → server: %s", method)

    # ── Schema conversion ─────────────────────────────────────────────────────

    @staticmethod
    def _parse_tool(raw: dict[str, Any]) -> ToolSchema:
        """Convert a raw MCP tool descriptor to a ToolSchema."""
        name: str = raw["name"]
        description: str = raw.get("description", "")
        input_schema: dict = raw.get("inputSchema", {})
        properties: dict = input_schema.get("properties", {})
        required_names: list[str] = input_schema.get("required", [])

        params: list[ToolParam] = []
        for pname, pdef in properties.items():
            params.append(
                ToolParam(
                    name=pname,
                    type=pdef.get("type", "string"),
                    description=pdef.get("description", ""),
                    required=pname in required_names,
                    enum=pdef.get("enum", []),
                    items=pdef.get("items"),
                )
            )

        return ToolSchema(name=name, description=description, params=params)

    @staticmethod
    def _extract_text(content: list[dict[str, Any]]) -> str:
        """Flatten MCP content blocks into a plain string."""
        parts: list[str] = []
        for block in content:
            btype = block.get("type", "text")
            if btype == "text":
                parts.append(block.get("text", ""))
            elif btype == "resource":
                resource = block.get("resource", {})
                text = resource.get("text", "")
                if text:
                    parts.append(text)
                else:
                    # Binary blob — show URI only
                    parts.append(f"[resource: {resource.get('uri', '')}]")
            else:
                # Unknown block type — serialise as JSON
                parts.append(json.dumps(block, ensure_ascii=False))
        return "\n".join(parts)
