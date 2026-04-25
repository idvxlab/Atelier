from __future__ import annotations
import asyncio
import shlex
from harness.types.tools import ToolSchema, ToolParam

SHELL_SCHEMA = ToolSchema(
    name="shell",
    description="Execute a shell command. Pass command as a list of strings.",
    params=[
        ToolParam(name="command", type="array", description="Command and arguments as a list, e.g. ['ls', '-la']"),
        ToolParam(name="cwd", type="string", description="Working directory", required=False),
        ToolParam(name="timeout", type="number", description="Timeout in seconds (default 30)", required=False),
    ],
)

async def shell_tool(
    command: list[str] | str,
    cwd: str = ".",
    timeout: float = 30.0,
) -> str:
    if isinstance(command, str):
        command = shlex.split(command)

    proc = await asyncio.create_subprocess_exec(
        *command,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        try:
            proc.kill()
            await proc.communicate()
        except Exception:
            pass
        return f"[Command timed out after {timeout}s]"

    return stdout.decode(errors="replace")
