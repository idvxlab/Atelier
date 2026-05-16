"""Tests for the MCP layer (stdio transport, client, bridge).

All tests use a tiny in-process "mock MCP Server" that speaks JSON-RPC 2.0
over a pair of asyncio streams — no npm / npx required.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from harness.config import HarnessConfig, MCPServerConfig
from harness.mcp.bridge import register_mcp_server
from harness.mcp.client import MCPClient, MCPError
from harness.mcp.stdio_transport import StdioTransport, TransportError
from harness.tools.registry import ToolRegistry

# ---------------------------------------------------------------------------
# Helpers: a tiny echo-style mock MCP Server launched as a subprocess
# ---------------------------------------------------------------------------

# This Python snippet is executed as a child process.  It reads JSON-RPC
# lines from stdin and writes back canned responses so we can exercise the
# real transport and client code end-to-end.
_MOCK_SERVER_SCRIPT = """\
import sys, json

TOOLS = [
    {
        "name": "echo",
        "description": "Echo back the input text.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to echo"}
            },
            "required": ["text"],
        },
    },
    {
        "name": "add",
        "description": "Add two numbers.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "a": {"type": "number", "description": "First operand"},
                "b": {"type": "number", "description": "Second operand"},
            },
            "required": ["a", "b"],
        },
    },
]

def respond(req, result):
    msg = {"jsonrpc": "2.0", "id": req["id"], "result": result}
    sys.stdout.write(json.dumps(msg) + "\\n")
    sys.stdout.flush()

for raw in sys.stdin:
    raw = raw.strip()
    if not raw:
        continue
    try:
        req = json.loads(raw)
    except Exception:
        continue

    method = req.get("method", "")
    rid    = req.get("id")      # None for notifications

    if method == "initialize":
        respond(req, {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "mock-server", "version": "0.0.1"},
        })
    elif method == "notifications/initialized":
        pass  # notification — no response
    elif method == "tools/list":
        respond(req, {"tools": TOOLS})
    elif method == "tools/call":
        name = req["params"]["name"]
        args = req["params"].get("arguments", {})
        if name == "echo":
            respond(req, {"content": [{"type": "text", "text": args.get("text", "")}]})
        elif name == "add":
            total = args.get("a", 0) + args.get("b", 0)
            respond(req, {"content": [{"type": "text", "text": str(total)}]})
        else:
            respond(req, {"isError": True, "content": [{"type": "text", "text": f"Unknown tool: {name}"}]})
    else:
        # Unknown method — return empty result
        if rid is not None:
            respond(req, {})
"""


def _mock_server_command() -> list[str]:
    """Return the command to start the in-process mock MCP Server."""
    return [sys.executable, "-c", _MOCK_SERVER_SCRIPT]


# ---------------------------------------------------------------------------
# StdioTransport unit tests
# ---------------------------------------------------------------------------

class TestStdioTransport:
    @pytest.mark.asyncio
    async def test_start_and_close(self):
        t = StdioTransport()
        await t.start(_mock_server_command())
        assert t._process is not None
        await t.close()
        assert t._process is None

    @pytest.mark.asyncio
    async def test_double_start_raises(self):
        t = StdioTransport()
        await t.start(_mock_server_command())
        try:
            with pytest.raises(TransportError, match="already started"):
                await t.start(_mock_server_command())
        finally:
            await t.close()

    @pytest.mark.asyncio
    async def test_send_not_started_raises(self):
        t = StdioTransport()
        with pytest.raises(TransportError, match="not started"):
            await t.send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})

    @pytest.mark.asyncio
    async def test_send_receive_initialize(self):
        t = StdioTransport()
        await t.start(_mock_server_command())
        try:
            rid = t.next_id()
            resp = await t.send({
                "jsonrpc": "2.0",
                "id": rid,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "0"},
                },
            })
            assert resp["result"]["protocolVersion"] == "2024-11-05"
        finally:
            await t.close()

    @pytest.mark.asyncio
    async def test_next_id_increments(self):
        t = StdioTransport()
        ids = [t.next_id() for _ in range(5)]
        assert ids == list(range(1, 6))


# ---------------------------------------------------------------------------
# MCPClient unit tests
# ---------------------------------------------------------------------------

class TestMCPClient:
    @pytest.mark.asyncio
    async def test_connect_and_close(self):
        client = MCPClient(server_name="test")
        await client.connect(_mock_server_command())
        assert client._connected
        await client.close()
        assert not client._connected

    @pytest.mark.asyncio
    async def test_list_tools_returns_schemas(self):
        client = MCPClient(server_name="test")
        await client.connect(_mock_server_command())
        try:
            schemas = await client.list_tools()
            names = [s.name for s in schemas]
            assert "echo" in names
            assert "add" in names
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_list_tools_schema_params(self):
        client = MCPClient(server_name="test")
        await client.connect(_mock_server_command())
        try:
            schemas = await client.list_tools()
            echo = next(s for s in schemas if s.name == "echo")
            assert len(echo.params) == 1
            assert echo.params[0].name == "text"
            assert echo.params[0].type == "string"
            assert echo.params[0].required is True
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_call_tool_echo(self):
        client = MCPClient(server_name="test")
        await client.connect(_mock_server_command())
        try:
            result = await client.call_tool("echo", {"text": "hello mcp"})
            assert result == "hello mcp"
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_call_tool_add(self):
        client = MCPClient(server_name="test")
        await client.connect(_mock_server_command())
        try:
            result = await client.call_tool("add", {"a": 3, "b": 4})
            assert result == "7"
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_call_tool_error_raises_mcp_error(self):
        client = MCPClient(server_name="test")
        await client.connect(_mock_server_command())
        try:
            with pytest.raises(MCPError, match="no_such_tool"):
                await client.call_tool("no_such_tool", {})
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_call_without_connect_raises(self):
        client = MCPClient()
        with pytest.raises(TransportError, match="not connected"):
            await client.list_tools()

    @pytest.mark.asyncio
    async def test_list_without_connect_raises(self):
        client = MCPClient()
        with pytest.raises(TransportError, match="not connected"):
            await client.call_tool("echo", {})


# ---------------------------------------------------------------------------
# Bridge unit tests
# ---------------------------------------------------------------------------

class TestBridge:
    @pytest.mark.asyncio
    async def test_register_mcp_server_no_prefix(self):
        client = MCPClient(server_name="test")
        await client.connect(_mock_server_command())
        try:
            registry = ToolRegistry()
            names = await register_mcp_server(registry, client)
            assert set(names) == {"echo", "add"}
            assert registry.get("echo") is not None
            assert registry.get("add") is not None
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_register_mcp_server_with_prefix(self):
        client = MCPClient(server_name="test")
        await client.connect(_mock_server_command())
        try:
            registry = ToolRegistry()
            names = await register_mcp_server(registry, client, prefix="myserver")
            assert "myserver__echo" in names
            assert "myserver__add" in names
            assert registry.get("myserver__echo") is not None
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_registered_tool_is_callable(self):
        """The registered handler should actually invoke the MCP tool."""
        client = MCPClient(server_name="test")
        await client.connect(_mock_server_command())
        try:
            registry = ToolRegistry()
            await register_mcp_server(registry, client)

            tool = registry.get("echo")
            assert tool is not None
            result = await tool.handler(text="ping")
            assert result == "ping"
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_returns_sorted_names(self):
        client = MCPClient(server_name="test")
        await client.connect(_mock_server_command())
        try:
            registry = ToolRegistry()
            names = await register_mcp_server(registry, client)
            assert names == sorted(names)
        finally:
            await client.close()


# ---------------------------------------------------------------------------
# Config parsing tests
# ---------------------------------------------------------------------------

class TestMCPConfig:
    def test_mcp_servers_default_empty(self):
        cfg = HarnessConfig()
        assert cfg.mcp_servers == {}

    def test_mcp_server_config_fields(self):
        sc = MCPServerConfig(transport="stdio", command=["npx", "some-server"])
        assert sc.transport == "stdio"
        assert sc.command == ["npx", "some-server"]

    def test_from_yaml_no_mcp_section(self, tmp_path: Path):
        yaml_content = "default_provider: test\nproviders: {}\n"
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml_content)
        cfg = HarnessConfig.from_yaml(str(cfg_file))
        assert cfg.mcp_servers == {}

    def test_from_yaml_with_mcp_servers(self, tmp_path: Path):
        yaml_content = (
            "default_provider: test\n"
            "providers: {}\n"
            "mcp_servers:\n"
            "  filesystem:\n"
            "    transport: stdio\n"
            "    command: [npx, -y, '@modelcontextprotocol/server-filesystem', '.']\n"
        )
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml_content)
        cfg = HarnessConfig.from_yaml(str(cfg_file))
        assert "filesystem" in cfg.mcp_servers
        sc = cfg.mcp_servers["filesystem"]
        assert sc.transport == "stdio"
        assert sc.command[0] == "npx"
        assert "@modelcontextprotocol/server-filesystem" in sc.command


# ---------------------------------------------------------------------------
# setup_mcp_servers integration test
# ---------------------------------------------------------------------------

class TestSetupMCPServers:
    @pytest.mark.asyncio
    async def test_setup_mcp_servers_registers_tools(self):
        from harness.factory import setup_mcp_servers

        cfg = HarnessConfig(
            mcp_servers={
                "mock": MCPServerConfig(
                    transport="stdio",
                    command=_mock_server_command(),
                )
            }
        )
        registry = ToolRegistry()
        clients = await setup_mcp_servers(registry, cfg)
        try:
            assert len(clients) == 1
            assert registry.get("mock__echo") is not None
            assert registry.get("mock__add") is not None
        finally:
            for c in clients:
                await c.close()

    @pytest.mark.asyncio
    async def test_setup_mcp_servers_skips_unknown_transport(self):
        from harness.factory import setup_mcp_servers

        cfg = HarnessConfig(
            mcp_servers={
                "bad": MCPServerConfig(transport="http", command=["dummy"])
            }
        )
        registry = ToolRegistry()
        clients = await setup_mcp_servers(registry, cfg)
        assert clients == []
        assert registry.discover() == []

    @pytest.mark.asyncio
    async def test_setup_mcp_servers_empty_config(self):
        from harness.factory import setup_mcp_servers

        cfg = HarnessConfig()
        registry = ToolRegistry()
        clients = await setup_mcp_servers(registry, cfg)
        assert clients == []
