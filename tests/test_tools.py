"""Tests for the tools layer."""
from __future__ import annotations

import sys

import pytest

from harness.tools.registry import ToolRegistry
from harness.tools.executor import ToolExecutor, LIMITS
from harness.tools.overflow import OverflowStore
from harness.tools.builtin.shell import SHELL_SCHEMA, shell_tool
from harness.tools.builtin.read_file import read_file_tool
from harness.tools.builtin.glob_tool import glob_tool
from harness.llm.base import LLMConfig
from harness.llm.openai_provider import OpenAIProvider
from harness.types.messages import ToolCallBlock
from harness.types.tools import ToolSchema, ToolParam
from harness.observability.events import EventEmitter


# ──────────────────────────────────────────────────────────────────────
# ToolRegistry
# ──────────────────────────────────────────────────────────────────────

class TestToolRegistry:
    def test_register_and_discover(self):
        reg = ToolRegistry()
        schema = ToolSchema(name="echo", description="Echo", params=[])
        reg.register(schema, lambda: None)
        tools = reg.discover()
        assert len(tools) == 1
        assert tools[0].schema.name == "echo"

    def test_discover_returns_fresh_list(self):
        reg = ToolRegistry()
        schema = ToolSchema(name="echo", description="Echo", params=[])
        reg.register(schema, lambda: None)
        list1 = reg.discover()
        list2 = reg.discover()
        assert list1 is not list2  # not the same object

    def test_unregister(self):
        reg = ToolRegistry()
        schema = ToolSchema(name="echo", description="Echo", params=[])
        reg.register(schema, lambda: None)
        reg.unregister("echo")
        assert reg.get("echo") is None
        assert len(reg.discover()) == 0

    def test_get_unknown_returns_none(self):
        reg = ToolRegistry()
        assert reg.get("nonexistent") is None


def test_openai_tool_schema_includes_array_items():
    provider = OpenAIProvider(LLMConfig(model="gpt-4o", api_key="sk-test"))

    tool = provider._to_openai_tool(SHELL_SCHEMA)

    command_schema = tool["function"]["parameters"]["properties"]["command"]
    assert command_schema["type"] == "array"
    assert command_schema["items"] == {"type": "string"}


# ──────────────────────────────────────────────────────────────────────
# ToolExecutor
# ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_executor_runs_tool():
    reg = ToolRegistry()
    schema = ToolSchema(name="greet", description="Greet", params=[
        ToolParam(name="name", type="string", description="Name")
    ])

    async def handler(name: str) -> str:
        return f"Hello, {name}!"

    reg.register(schema, handler)
    emitter = EventEmitter("test")
    overflow = OverflowStore()
    executor = ToolExecutor(registry=reg, overflow=overflow, emitter=emitter)

    calls = [ToolCallBlock(tool_call_id="c1", tool_name="greet", tool_input={"name": "World"})]
    results = await executor.execute_all(calls, round_idx=0)

    assert len(results) == 1
    assert results[0].content == "Hello, World!"
    assert not results[0].is_error


@pytest.mark.asyncio
async def test_executor_handles_unknown_tool():
    reg = ToolRegistry()
    emitter = EventEmitter("test")
    overflow = OverflowStore()
    executor = ToolExecutor(registry=reg, overflow=overflow, emitter=emitter)

    calls = [ToolCallBlock(tool_call_id="c1", tool_name="missing", tool_input={})]
    results = await executor.execute_all(calls, round_idx=0)

    assert results[0].is_error
    assert "not found" in results[0].content


@pytest.mark.asyncio
async def test_executor_overflow():
    reg = ToolRegistry()
    schema = ToolSchema(name="big_output", description="Big", params=[])

    async def handler() -> str:
        return "x" * 100_000  # well over any limit

    reg.register(schema, handler)
    emitter = EventEmitter("test")
    overflow = OverflowStore()
    executor = ToolExecutor(registry=reg, overflow=overflow, emitter=emitter)

    calls = [ToolCallBlock(tool_call_id="c1", tool_name="big_output", tool_input={})]
    results = await executor.execute_all(calls, round_idx=0)

    assert results[0].is_overflow_ref
    assert "ref:" in results[0].content


@pytest.mark.asyncio
async def test_executor_tool_exception():
    reg = ToolRegistry()
    schema = ToolSchema(name="fail", description="Fails", params=[])

    async def handler() -> str:
        raise RuntimeError("boom")

    reg.register(schema, handler)
    emitter = EventEmitter("test")
    overflow = OverflowStore()
    executor = ToolExecutor(registry=reg, overflow=overflow, emitter=emitter)

    calls = [ToolCallBlock(tool_call_id="c1", tool_name="fail", tool_input={})]
    results = await executor.execute_all(calls, round_idx=0)

    assert results[0].is_error
    assert "boom" in results[0].content


# ──────────────────────────────────────────────────────────────────────
# Builtin tools
# ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_shell_tool_basic():
    result = await shell_tool(command=["echo", "hello"])
    assert "hello" in result


@pytest.mark.asyncio
async def test_shell_tool_accepts_string():
    result = await shell_tool(command="echo world")
    assert "world" in result


@pytest.mark.asyncio
async def test_shell_tool_timeout():
    result = await shell_tool(
        command=[sys.executable, "-c", "import time; time.sleep(10)"],
        timeout=0.1,
    )
    assert "timed out" in result.lower()


@pytest.mark.asyncio
async def test_glob_tool_returns_files_only(tmp_path):
    (tmp_path / "actual.py").write_text("print('hello')\n", encoding="utf-8")
    (tmp_path / "folder.py").mkdir()

    result = await glob_tool(pattern="*.py", path=str(tmp_path))

    assert "actual.py" in result
    assert "folder.py" not in result


@pytest.mark.asyncio
async def test_read_file_tool(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("line1\nline2\nline3\n")
    result = await read_file_tool(path=str(f))
    assert "line1" in result
    assert "line3" in result


@pytest.mark.asyncio
async def test_read_file_tool_not_found():
    result = await read_file_tool(path="/nonexistent/file.txt")
    assert "Error" in result


@pytest.mark.asyncio
async def test_read_file_tool_offset_limit(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("\n".join(f"line{i}" for i in range(10)) + "\n")
    result = await read_file_tool(path=str(f), offset=2, limit=3)
    assert "line2" in result
    assert "line4" in result
    assert "line5" not in result
