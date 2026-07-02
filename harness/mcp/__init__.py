"""MCP (Model Context Protocol) support for MyHarness.

Provides stdio transport, JSON-RPC client, and a bridge to ToolRegistry
so any MCP Server's tools can be used as native harness tools.
"""
from harness.mcp.stdio_transport import StdioTransport
from harness.mcp.http_transport import HttpTransport
from harness.mcp.client import MCPClient
from harness.mcp.bridge import register_mcp_server

__all__ = ["StdioTransport", "HttpTransport", "MCPClient", "register_mcp_server"]
