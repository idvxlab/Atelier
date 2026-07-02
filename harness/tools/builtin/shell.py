from __future__ import annotations
import asyncio
import logging
import os
import shlex
import shutil
import subprocess
import sys
import time
from harness.types.tools import ToolSchema, ToolParam

logger = logging.getLogger("harness.shell")

SHELL_SCHEMA = ToolSchema(
    name="shell",
    description=(
        "Execute a program directly (no shell interpreter). "
        "Pass command as a list, e.g. ['git', 'status'] or ['python', 'script.py']. "
        "Use this for running executables like git, python, pip, npm, etc. "
        "Does NOT support shell syntax (pipes |, redirects >, glob * expansion, $VAR). "
        "Use powershell if you need shell scripting features on Windows."
    ),
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
    else:
        command = [str(part) for part in command]

    if not command:
        return "Error: command must not be empty."

    merged_env: dict[str, str] | None = None
    if env:
        merged_env = {**os.environ, **{str(k): str(v) for k, v in env.items()}}

    executable = command[0]
    path_env = (merged_env or os.environ).get("PATH", "")
    resolved = shutil.which(executable, path=path_env)
    used_python_fallback = False

    # On Windows or isolated envs, the server process may not inherit a PATH entry
    # for "python" even though the current interpreter is available.
    if resolved is None and executable in {"python", "python3"} and sys.executable:
        command = [sys.executable, *command[1:]]
        used_python_fallback = True

    logger.info(
        "shell.start command=%r cwd=%r timeout=%ss resolved=%r python_fallback=%s extra_env=%s",
        command,
        cwd,
        timeout,
        resolved,
        used_python_fallback,
        sorted(env.keys()) if env else [],
    )
    started_at = time.perf_counter()

    try:
        completed = await asyncio.to_thread(
            subprocess.run,
            command,
            cwd=cwd,
            env=merged_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
            timeout=timeout,
            check=False,
            shell=False,
        )
    except FileNotFoundError:
        elapsed = time.perf_counter() - started_at
        logger.warning(
            "shell.file_not_found command=%r cwd=%r elapsed=%.3fs",
            command,
            cwd,
            elapsed,
        )
        return (
            f"Error: command not found: {command[0]!r}. "
            "On Windows, Unix commands like 'ls', 'cat', 'find', 'grep' do not exist. "
            "Use the built-in tools instead: glob (list files), read_file (read file), "
            "search/grep (search content), or powershell for Windows shell commands."
        )
    except PermissionError as exc:
        elapsed = time.perf_counter() - started_at
        logger.warning(
            "shell.permission_error command=%r cwd=%r elapsed=%.3fs error=%s",
            command,
            cwd,
            elapsed,
            exc,
        )
        return f"Error: permission denied running {command[0]!r}: {exc}"
    except OSError as exc:
        elapsed = time.perf_counter() - started_at
        logger.warning(
            "shell.os_error command=%r cwd=%r elapsed=%.3fs error=%s",
            command,
            cwd,
            elapsed,
            exc,
        )
        return f"Error: failed to start process {command[0]!r}: {exc}"
    except subprocess.TimeoutExpired:
        elapsed = time.perf_counter() - started_at
        logger.warning(
            "shell.timeout command=%r cwd=%r elapsed=%.3fs timeout=%ss",
            command,
            cwd,
            elapsed,
            timeout,
        )
        return f"[Command timed out after {timeout}s]"

    stdout_text = completed.stdout.decode(errors="replace")
    stderr_text = completed.stderr.decode(errors="replace")
    exit_code = completed.returncode
    elapsed = time.perf_counter() - started_at

    logger.info(
        "shell.done command=%r cwd=%r elapsed=%.3fs exit_code=%s stdout_len=%s stderr_len=%s",
        command,
        cwd,
        elapsed,
        exit_code,
        len(stdout_text),
        len(stderr_text),
    )

    parts: list[str] = []
    if stdout_text:
        parts.append(stdout_text.rstrip("\n"))
    if stderr_text:
        parts.append(f"[stderr]\n{stderr_text.rstrip(chr(10))}")
    parts.append(f"[exit code: {exit_code}]")

    return "\n".join(parts)
