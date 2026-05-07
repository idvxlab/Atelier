from __future__ import annotations
import asyncio
import os
import shlex
from harness.types.tools import ToolSchema, ToolParam

SHELL_SCHEMA = ToolSchema(
    name="shell",
    description="Execute a shell command and return stdout, stderr, and exit code separately.",
    params=[
        ToolParam(
            name="command",
            type="array",
            description="Command and arguments as a list, e.g. ['ls', '-la']",
            items={"type": "string"},
        ),
        ToolParam(name="cwd", type="string", description="Working directory", required=False),
        ToolParam(name="timeout", type="number", description="Timeout in seconds (default 30)", required=False),
        ToolParam(
            name="env",
            type="object",
            description="Extra environment variables to inject (merged with current env)",
            required=False,
        ),
    ],
)


async def shell_tool(
    command: list[str] | str,
    cwd: str = ".",
    timeout: float = 30.0,
    env: dict[str, str] | None = None,
) -> str:
    if isinstance(command, str):
        command = shlex.split(command)

    merged_env: dict[str, str] | None = None
    if env:
        merged_env = {**os.environ, **{str(k): str(v) for k, v in env.items()}}

    proc = await asyncio.create_subprocess_exec(
        *command,
        cwd=cwd,
        env=merged_env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        try:
            proc.kill()
            await proc.communicate()
        except Exception:
            pass
        return f"[Command timed out after {timeout}s]"

    stdout_text = stdout_bytes.decode(errors="replace")
    stderr_text = stderr_bytes.decode(errors="replace")
    exit_code = proc.returncode

    parts: list[str] = []
    if stdout_text:
        parts.append(stdout_text.rstrip("\n"))
    if stderr_text:
        parts.append(f"[stderr]\n{stderr_text.rstrip(chr(10))}")
    parts.append(f"[exit code: {exit_code}]")

    return "\n".join(parts)
