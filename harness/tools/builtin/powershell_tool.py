from __future__ import annotations

import asyncio
import shutil
import sys

from harness.types.tools import ToolSchema, ToolParam

POWERSHELL_SCHEMA = ToolSchema(
    name="powershell",
    description=(
        "Execute a PowerShell script and return stdout, stderr, and exit code separately. "
        "On Windows, uses pwsh.exe (falls back to powershell.exe); "
        "on Linux/macOS, uses pwsh."
    ),
    params=[
        ToolParam(
            name="script",
            type="string",
            description="PowerShell script to execute.",
        ),
        ToolParam(
            name="cwd",
            type="string",
            description="Working directory (defaults to current directory).",
            required=False,
        ),
        ToolParam(
            name="timeout",
            type="number",
            description="Timeout in seconds (default 30).",
            required=False,
        ),
    ],
)


def _find_powershell() -> str:
    """Return the PowerShell executable path appropriate for the current OS."""
    if sys.platform == "win32":
        for exe in ("pwsh.exe", "powershell.exe"):
            if shutil.which(exe):
                return exe
        return "powershell.exe"
    return "pwsh"


async def powershell_tool(
    script: str,
    cwd: str = ".",
    timeout: float = 30.0,
) -> str:
    exe = _find_powershell()
    proc = await asyncio.create_subprocess_exec(
        exe,
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        script,
        cwd=cwd,
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
        return f"[PowerShell timed out after {timeout}s]"

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
