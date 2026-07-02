from types import SimpleNamespace

import api.rest as rest_mod
from api.rest import _is_tool_inventory_query, _render_tool_inventory
from harness.config import HarnessConfig, MCPServerConfig
from harness.types.tools import ToolSchema


def test_is_tool_inventory_query_supports_chinese() -> None:
    assert _is_tool_inventory_query("请列出你当前可用的工具，特别是 filesystem 相关")
    assert _is_tool_inventory_query("现在有哪些工具")
    assert not _is_tool_inventory_query("请用 search 工具搜索 asyncio")


def test_render_tool_inventory_groups_mcp_tools() -> None:
    engine = SimpleNamespace(
        tool_schemas=[
            ToolSchema(name="read_file", description="Read a file", params=[]),
            ToolSchema(name="filesystem__read_text_file", description="Read text", params=[]),
        ]
    )

    text = _render_tool_inventory(engine)

    assert "filesystem__read_text_file" in text
    assert "MCP 工具" in text
    assert "内建工具" in text


def test_render_tool_inventory_warns_when_mcp_configured_but_missing() -> None:
    previous = rest_mod._config
    rest_mod._config = HarnessConfig(
        mcp_servers={"filesystem": MCPServerConfig(transport="stdio", command=["dummy"])}
    )
    try:
        engine = SimpleNamespace(
            tool_schemas=[ToolSchema(name="read_file", description="Read a file", params=[])]
        )
        text = _render_tool_inventory(engine)
        assert "已配置 MCP 服务器" in text
        assert "filesystem" in text
    finally:
        rest_mod._config = previous
