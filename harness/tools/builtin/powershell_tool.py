from __future__ import annotations

import asyncio
import shutil
import subprocess
import sys

from harness.types.tools import ToolSchema, ToolParam

POWERSHELL_SCHEMA = ToolSchema(
    name="powershell",
    description=(
        "Execute a PowerShell script with full shell scripting support "
        "(pipes |, variables $var, cmdlets like Get-ChildItem, conditionals, loops). "
        "Use this instead of shell when you need shell syntax or Windows-specific commands. "
        "On Windows uses pwsh.exe (falls back to powershell.exe); on Linux/macOS uses pwsh."
    ),
    params=[
        ToolParam(
            name="script",
            type="string",
            description="PowerShell script to execute.",
            required=False,
        ),
        ToolParam(
            name="command",
            type="string",
            description="Alias of script for compatibility with models that emit command instead of script.",
            required=False,
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
    script: str = "",
    command: str = "",
    cwd: str = ".",
    timeout: float = 30.0,
) -> str:
    script = script or command
    if not script.strip():
        return "Error: script is required."

    exe = _find_powershell()
    try:
        completed = await asyncio.to_thread(
            subprocess.run,
            [exe, "-NoProfile", "-NonInteractive", "-Command", script],
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
            timeout=timeout,
            check=False,
            shell=False,
        )
    except FileNotFoundError:
        return f"Error: PowerShell executable not found: {exe!r}"
    except PermissionError as exc:
        return f"Error: permission denied running {exe!r}: {exc}"
    except OSError as exc:
        return f"Error: failed to start PowerShell {exe!r}: {exc}"
    except subprocess.TimeoutExpired:
        return f"[PowerShell timed out after {timeout}s]"

    stdout_text = completed.stdout.decode(errors="replace")
    stderr_text = completed.stderr.decode(errors="replace")
    exit_code = completed.returncode

    parts: list[str] = []
    if stdout_text:
        parts.append(stdout_text.rstrip("\n"))
    if stderr_text:
        parts.append(f"[stderr]\n{stderr_text.rstrip(chr(10))}")
    parts.append(f"[exit code: {exit_code}]")

    return "\n".join(parts)
