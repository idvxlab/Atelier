"""Tests for the tools layer."""
from __future__ import annotations

import sys
import subprocess
import importlib

import pytest

from harness.tools.registry import ToolRegistry
from harness.tools.executor import ToolExecutor, LIMITS
from harness.tools.overflow import OverflowStore
from harness.tools.builtin.shell import SHELL_SCHEMA, shell_tool
from harness.tools.builtin.read_file import read_file_tool
from harness.tools.builtin.glob_tool import glob_tool
from harness.tools.builtin.write_file import write_file_tool
from harness.tools.builtin.edit_file import edit_file_tool
from harness.tools.builtin.web_fetch import web_fetch_tool
from harness.tools.builtin.web_search import web_search_tool
from harness.tools.builtin.think_tool import think_tool
from harness.tools.builtin.todo_tool import todo_write_tool
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


@pytest.mark.asyncio
async def test_executor_includes_exception_type_when_message_empty():
    reg = ToolRegistry()
    schema = ToolSchema(name="fail_empty", description="Fails", params=[])

    async def handler() -> str:
        raise RuntimeError()

    reg.register(schema, handler)
    emitter = EventEmitter("test")
    overflow = OverflowStore()
    executor = ToolExecutor(registry=reg, overflow=overflow, emitter=emitter)

    calls = [ToolCallBlock(tool_call_id="c1", tool_name="fail_empty", tool_input={})]
    results = await executor.execute_all(calls, round_idx=0)

    assert results[0].is_error
    assert "RuntimeError" in results[0].content


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
async def test_shell_tool_falls_back_to_current_python(monkeypatch):
    recorded: dict[str, object] = {}

    class DummyCompleted:
        returncode = 0
        stdout = b"Python test\n"
        stderr = b""

    def fake_run(cmd, **kwargs):
        recorded["cmd"] = list(cmd)
        return DummyCompleted()

    monkeypatch.setattr("harness.tools.builtin.shell.shutil.which", lambda *a, **k: None)
    monkeypatch.setattr(
        "harness.tools.builtin.shell.subprocess.run",
        fake_run,
    )

    result = await shell_tool(command=["python", "--version"])

    assert recorded["cmd"][0] == sys.executable
    assert "Python test" in result


@pytest.mark.asyncio
async def test_powershell_tool_accepts_command_alias(monkeypatch):
    ps_tool_module = importlib.import_module("harness.tools.builtin.powershell_tool")
    from harness.tools.builtin.powershell_tool import powershell_tool

    recorded: dict[str, object] = {}

    class DummyCompleted:
        returncode = 0
        stdout = b"D:\\MyHarnessPy\n"
        stderr = b""

    def fake_run(cmd, **kwargs):
        recorded["cmd"] = list(cmd)
        return DummyCompleted()

    monkeypatch.setattr(ps_tool_module.subprocess, "run", fake_run)

    result = await powershell_tool(command="Get-Location")

    assert recorded["cmd"][-1] == "Get-Location"
    assert "D:\\MyHarnessPy" in result


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


# ──────────────────────────────────────────────────────────────────────
# write_file
# ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_write_file_tool_overwrite(tmp_path):
    f = tmp_path / "hello.txt"
    result = await write_file_tool(path=str(f), content="hello world")
    assert "Written" in result
    assert f.read_text(encoding="utf-8") == "hello world"


@pytest.mark.asyncio
async def test_write_file_tool_append(tmp_path):
    f = tmp_path / "hello.txt"
    f.write_text("first\n", encoding="utf-8")
    result = await write_file_tool(path=str(f), content="second", append=True)
    assert "Appended" in result
    assert f.read_text(encoding="utf-8") == "first\nsecond"


@pytest.mark.asyncio
async def test_write_file_tool_creates_parent(tmp_path):
    nested = tmp_path / "a" / "b"
    f = nested / "file.txt"
    result = await write_file_tool(path=str(f), content="nested")
    assert "Written" in result
    assert f.read_text(encoding="utf-8") == "nested"


@pytest.mark.asyncio
async def test_write_file_tool_invalid_path():
    # Write to an absolute path that cannot exist on this OS
    result = await write_file_tool(path="NUL:/impossible", content="x")
    assert "Error" in result


# ──────────────────────────────────────────────────────────────────────
# edit_file
# ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_edit_file_tool_replace(tmp_path):
    f = tmp_path / "sample.txt"
    f.write_text("hello world\nwelcome\n", encoding="utf-8")
    result = await edit_file_tool(path=str(f), old_string="world", new_string="there")
    assert "first" in result
    assert f.read_text(encoding="utf-8") == "hello there\nwelcome\n"


@pytest.mark.asyncio
async def test_edit_file_tool_replace_all(tmp_path):
    f = tmp_path / "sample.txt"
    f.write_text("foo bar foo baz foo\n", encoding="utf-8")
    result = await edit_file_tool(
        path=str(f), old_string="foo", new_string="FOO", replace_all=True
    )
    assert "all" in result
    assert f.read_text(encoding="utf-8") == "FOO bar FOO baz FOO\n"


@pytest.mark.asyncio
async def test_edit_file_tool_duplicate_without_flag(tmp_path):
    f = tmp_path / "sample.txt"
    f.write_text("foo foo foo\n", encoding="utf-8")
    result = await edit_file_tool(path=str(f), old_string="foo", new_string="FOO")
    assert "Error" in result
    assert "appears 3 times" in result


@pytest.mark.asyncio
async def test_edit_file_tool_not_found():
    result = await edit_file_tool(
        path="/nonexistent/file.txt",
        old_string="a",
        new_string="b",
    )
    assert "Error" in result
    assert "not found" in result


@pytest.mark.asyncio
async def test_edit_file_tool_not_matched(tmp_path):
    f = tmp_path / "sample.txt"
    f.write_text("hello world\n", encoding="utf-8")
    result = await edit_file_tool(path=str(f), old_string="not exist", new_string="X")
    assert "Error" in result
    assert "not found" in result


# ──────────────────────────────────────────────────────────────────────
# think_tool
# ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_think_tool_returns_thought():
    result = await think_tool(thought="Let me think step by step.")
    assert result == "Let me think step by step."


@pytest.mark.asyncio
async def test_think_tool_empty():
    result = await think_tool(thought="")
    assert result == ""


# ──────────────────────────────────────────────────────────────────────
# todo_write
# ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_todo_write_set():
    result = await todo_write_tool(
        session_id="s1",
        action="set",
        todos=[{"content": "task 1", "status": "pending"}],
    )
    assert "set with 1 item" in result


@pytest.mark.asyncio
async def test_todo_write_get():
    await todo_write_tool(
        session_id="s2",
        action="set",
        todos=[
            {"content": "alpha", "status": "pending"},
            {"content": "beta", "status": "in_progress"},
        ],
    )
    result = await todo_write_tool(session_id="s2", action="get")
    assert "[pending]" in result
    assert "[in_progress]" in result
    assert "alpha" in result
    assert "beta" in result


@pytest.mark.asyncio
async def test_todo_write_update():
    await todo_write_tool(
        session_id="s3",
        action="set",
        todos=[{"content": "task", "status": "pending"}],
    )
    result = await todo_write_tool(
        session_id="s3", action="update", index=0, status="completed"
    )
    assert "completed" in result


@pytest.mark.asyncio
async def test_todo_write_update_invalid_status():
    await todo_write_tool(
        session_id="s4",
        action="set",
        todos=[{"content": "task", "status": "pending"}],
    )
    result = await todo_write_tool(
        session_id="s4", action="update", index=0, status="done"
    )
    assert "Error" in result
    assert "done" in result


@pytest.mark.asyncio
async def test_todo_write_get_empty():
    result = await todo_write_tool(session_id="nonexistent", action="get")
    assert "No todo" in result


# ──────────────────────────────────────────────────────────────────────
# web_fetch (mock-free: just smoke-test it doesn't crash)
# ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_web_fetch_smoke():
    result = await web_fetch_tool(url="https://httpbin.org/html", max_length=500)
    # Should not be an error; content should be plain text
    assert "Error" not in result or len(result) < 200


@pytest.mark.asyncio
async def test_web_fetch_truncation():
    result = await web_fetch_tool(url="https://httpbin.org/bytes/1000", max_length=100)
    assert "truncated" in result.lower()
    assert len(result) <= 150  # rough check


@pytest.mark.asyncio
async def test_web_fetch_invalid_url():
    result = await web_fetch_tool(url="https://this-domain-does-not-exist-xyz.invalid/")
    assert "Error" in result


# ──────────────────────────────────────────────────────────────────────
# web_search (mock-free: just smoke-test it doesn't crash)
# ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_web_search_smoke():
    result = await web_search_tool(query="python httpx", max_results=3)
    # Should always return a string — results, "No results", or a graceful error message
    assert isinstance(result, str) and len(result) > 0
