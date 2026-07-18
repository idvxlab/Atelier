from types import SimpleNamespace

import api.rest as rest_mod
from api.rest import (
    _is_tool_inventory_query,
    _is_task_execution_request,
    _render_tool_inventory,
    _TOOL_QUERY_PATTERNS,
    _TOOL_QUERY_KEYWORDS_ZH,
    _TASK_EXECUTION_KEYWORDS,
)
from harness.config import HarnessConfig, MCPServerConfig
from harness.types.tools import ToolSchema


# ─── _is_tool_inventory_query tests ────────────────────────────────────────

class TestToolInventoryQueryEnglish:
    """English patterns should work as before."""

    def test_list_tools(self) -> None:
        assert _is_tool_inventory_query("list tools")
        assert _is_tool_inventory_query("list available tools")
        assert _is_tool_inventory_query("what tools do you have")
        assert _is_tool_inventory_query("show tools")
        assert _is_tool_inventory_query("which tools are available")

    def test_not_a_query(self) -> None:
        assert not _is_tool_inventory_query("use the search tool to find docs")
        assert not _is_tool_inventory_query("call the shell tool")
        assert not _is_tool_inventory_query("tool testing pipeline")


class TestToolInventoryQueryChinese:
    """Chinese patterns must form complete phrases — no partial matches."""

    def test_explicit_list_queries(self) -> None:
        """Direct queries about available tools should trigger the shortcut."""
        assert _is_tool_inventory_query("列出工具")
        assert _is_tool_inventory_query("列出可用工具")
        assert _is_tool_inventory_query("列出所有工具")
        assert _is_tool_inventory_query("列出功能")

    def test_what_tools_queries(self) -> None:
        assert _is_tool_inventory_query("有哪些工具")
        assert _is_tool_inventory_query("有哪些可用工具")
        assert _is_tool_inventory_query("哪些工具可用")
        assert _is_tool_inventory_query("有什么工具")

    def test_current_tools_queries(self) -> None:
        assert _is_tool_inventory_query("当前工具")
        assert _is_tool_inventory_query("当前可用工具")
        assert _is_tool_inventory_query("现在有哪些工具")

    def test_show_view_queries(self) -> None:
        assert _is_tool_inventory_query("显示工具")
        assert _is_tool_inventory_query("显示可用工具")
        assert _is_tool_inventory_query("查看工具列表")
        assert _is_tool_inventory_query("看看工具")

    def test_tool_list_reference(self) -> None:
        assert _is_tool_inventory_query("工具列表")
        assert _is_tool_inventory_query("功能清单")

    # ── These must NOT trigger the shortcut ───────────────────────────────

    def test_tool_chain_not_query(self) -> None:
        """'工具链' is a task, not a tool list query."""
        assert not _is_tool_inventory_query("工具链测试")
        assert not _is_tool_inventory_query("工具链验收")
        assert not _is_tool_inventory_query("执行工具链")
        assert not _is_tool_inventory_query("设计工具链")

    def test_tool_execution_not_query(self) -> None:
        assert not _is_tool_inventory_query("工具调用测试")
        assert not _is_tool_inventory_query("工具执行流程")
        assert not _is_tool_inventory_query("工具开发")
        assert not _is_tool_inventory_query("工具使用")

    def test_mixed_task_not_query(self) -> None:
        assert not _is_tool_inventory_query("请用 search 工具搜索 asyncio")
        assert not _is_tool_inventory_query("调用 image_generate 生成图片")
        assert not _is_tool_inventory_query("使用 artifact_lint 验证")


# ─── _is_task_execution_request tests ─────────────────────────────────────

class TestTaskExecutionRequest:
    """_is_task_execution_request should return True for task-oriented requests."""

    # Basic keywords
    def test_execution_keywords(self) -> None:
        assert _is_task_execution_request("执行一次工具链验收测试")
        assert _is_task_execution_request("测试 image_generate")
        assert _is_task_execution_request("验收设计系统")
        assert _is_task_execution_request("运行工具链")
        assert _is_task_execution_request("创建 design run")
        assert _is_task_execution_request("生成设计稿")
        assert _is_task_execution_request("调用工具")
        assert _is_task_execution_request("完成任务")
        assert _is_task_execution_request("实施计划")
        assert _is_task_execution_request("开始构建")
        assert _is_task_execution_request("设计一个 AI 系统")

    def test_development_keywords(self) -> None:
        assert _is_task_execution_request("开发新功能")
        assert _is_task_execution_request("实现算法")
        assert _is_task_execution_request("处理数据")
        assert _is_task_execution_request("操作文件")
        assert _is_task_execution_request("制作报告")

    def test_technical_keywords(self) -> None:
        assert _is_task_execution_request("编写代码")
        assert _is_task_execution_request("调试问题")
        assert _is_task_execution_request("修复 bug")
        assert _is_task_execution_request("优化性能")
        assert _is_task_execution_request("分析日志")
        assert _is_task_execution_request("检查配置")
        assert _is_task_execution_request("验证结果")
        assert _is_task_execution_request("导出数据")

    def test_not_task_requests(self) -> None:
        """Pure tool queries should NOT be task requests."""
        assert not _is_task_execution_request("有哪些工具")
        assert not _is_task_execution_request("列出可用工具")
        assert not _is_task_execution_request("当前有哪些工具可用")
        assert not _is_task_execution_request("工具列表")
        assert not _is_task_execution_request("show tools")


# ─── Routing decision tests ─────────────────────────────────────────────────

class TestRoutingDecision:
    """Combined routing: tool query WITHOUT task keywords → shortcut.

    Tool query WITH task keywords → enters Agent Loop.
    """

    def test_pure_tool_query_goes_local(self) -> None:
        """Case 1: '有哪些工具？' → local shortcut (no task keywords)."""
        text = "有哪些工具？"
        is_query = _is_tool_inventory_query(text)
        is_task = _is_task_execution_request(text)
        # is_query=True, is_task=False → shortcut
        assert is_query
        assert not is_task

    def test_task_with_tools_enters_loop(self) -> None:
        """Case 2: '请执行一次工具链完整验收测试，需要实际调用工具。' → loop."""
        text = "请执行一次工具链完整验收测试，需要实际调用工具。"
        is_query = _is_tool_inventory_query(text)
        is_task = _is_task_execution_request(text)
        # is_query may or may not be True, but is_task=True → enters loop
        assert is_task
        # The key assertion: because is_task=True, the shortcut is skipped

    def test_design_task_with_tools_enters_loop(self) -> None:
        """Case 3: '设计一个 AI Design Harness，需要调用 image_generate 和 artifact_lint。'"""
        text = "设计一个 AI Design Harness，需要调用 image_generate 和 artifact_lint。"
        is_query = _is_tool_inventory_query(text)
        is_task = _is_task_execution_request(text)
        assert is_task
        assert not is_query  # "设计" alone doesn't match our strict patterns

    def test_explicit_list_with_execution_intent(self) -> None:
        """Case 4: '列出当前可用工具，然后执行测试' → loop (has task keywords)."""
        text = "列出当前可用工具，然后执行测试"
        is_query = _is_tool_inventory_query(text)
        is_task = _is_task_execution_request(text)
        # Both could be True, but is_task=True blocks the shortcut
        assert is_task

    def test_original_bug_case(self) -> None:
        """The original bug: '设计工具链完整验收测试' was wrongly intercepted."""
        text = '请作为主智能体执行一次"设计工具链完整验收测试"。你必须创建一个新的 design run，然后按顺序调用不同子智能体分别测试每一类工具。'
        is_query = _is_tool_inventory_query(text)
        is_task = _is_task_execution_request(text)
        # This should NOT be a pure tool query
        assert not is_query, "工具链完整验收测试 is NOT a tool list query"
        # But it IS a task request
        assert is_task, "执行一次...验收测试 IS a task request"


# ─── _render_tool_inventory tests (unchanged) ───────────────────────────────

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
