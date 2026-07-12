from __future__ import annotations

import asyncio
import os
import shlex
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from harness.types.tools import ToolParam, ToolSchema


BACKGROUND_TASK_SCHEMA = ToolSchema(
    name="background_task",
    description=(
        "Run and manage long-running commands in the background. "
        "Use action=start to launch a command, action=status to inspect one, "
        "action=list to list recent tasks, and action=cancel to stop a running task."
    ),
    params=[
        ToolParam(
            name="action",
            type="string",
            description="Action: start, status, list, or cancel.",
        ),
        ToolParam(
            name="command",
            type="array",
            description="Command and arguments for action=start, e.g. ['python', '-m', 'pytest'].",
            required=False,
            items={"type": "string"},
        ),
        ToolParam(name="task_id", type="string", description="Background task id.", required=False),
        ToolParam(name="cwd", type="string", description="Working directory for action=start.", required=False),
        ToolParam(name="timeout", type="number", description="Timeout in seconds for action=start.", required=False),
        ToolParam(
            name="env",
            type="object",
            description="Extra environment variables for action=start.",
            required=False,
        ),
    ],
)


@dataclass
class BackgroundTask:
    task_id: str
    command: list[str]
    cwd: str = "."
    timeout: float = 300.0
    status: str = "running"
    started_at: float = field(default_factory=time.time)
    completed_at: float | None = None
    exit_code: int | None = None
    output: str = ""
    error: str = ""
    _process: subprocess.Popen | None = field(default=None, repr=False)

    def to_dict(self, output_limit: int = 4000) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "command": self.command,
            "cwd": self.cwd,
            "timeout": self.timeout,
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "exit_code": self.exit_code,
            "output": self.output[:output_limit],
            "error": self.error[:output_limit],
        }


class BackgroundTaskManager:
    def __init__(self) -> None:
        self._tasks: dict[str, BackgroundTask] = {}
        self._lock = asyncio.Lock()

    async def start(
        self,
        command: list[str] | str,
        cwd: str = ".",
        timeout: float = 300.0,
        env: dict[str, str] | None = None,
    ) -> BackgroundTask:
        prepared = _prepare_command(command, env)
        task = BackgroundTask(
            task_id=f"bg_{uuid.uuid4().hex[:8]}",
            command=prepared.command,
            cwd=cwd or ".",
            timeout=float(timeout or 300.0),
        )
        async with self._lock:
            self._tasks[task.task_id] = task
        asyncio.create_task(self._run(task, prepared.env))
        return task

    async def get(self, task_id: str) -> BackgroundTask | None:
        async with self._lock:
            return self._tasks.get(task_id)

    async def list(self) -> list[BackgroundTask]:
        async with self._lock:
            return sorted(self._tasks.values(), key=lambda item: item.started_at, reverse=True)

    async def cancel(self, task_id: str) -> bool:
        task = await self.get(task_id)
        if task is None or task.status != "running":
            return False
        proc = task._process
        if proc is not None and proc.poll() is None:
            proc.terminate()
        task.status = "cancelled"
        task.completed_at = time.time()
        return True

    async def _run(self, task: BackgroundTask, env: dict[str, str] | None) -> None:
        try:
            proc = await asyncio.to_thread(
                subprocess.Popen,
                task.command,
                cwd=task.cwd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=False,
                shell=False,
            )
            task._process = proc
            try:
                stdout, stderr = await asyncio.to_thread(
                    proc.communicate,
                    timeout=task.timeout,
                )
                task.exit_code = proc.returncode
                task.output = (stdout or b"").decode(errors="replace").strip()
                task.error = (stderr or b"").decode(errors="replace").strip()
                if task.status != "cancelled":
                    task.status = "completed" if proc.returncode == 0 else "failed"
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout, stderr = await asyncio.to_thread(proc.communicate)
                task.exit_code = proc.returncode
                task.output = (stdout or b"").decode(errors="replace").strip()
                task.error = ((stderr or b"").decode(errors="replace").strip() + "\n[timeout]").strip()
                task.status = "timeout"
        except Exception as exc:
            task.status = "failed"
            task.error = str(exc)
        finally:
            task.completed_at = task.completed_at or time.time()
            task._process = None


@dataclass
class _PreparedCommand:
    command: list[str]
    env: dict[str, str] | None = None


_MANAGER = BackgroundTaskManager()


async def background_task_tool(
    action: str,
    command: list[str] | str | None = None,
    task_id: str = "",
    cwd: str = ".",
    timeout: float = 300.0,
    env: dict[str, str] | None = None,
) -> str:
    action = (action or "").strip().lower()
    if action == "start":
        if command is None:
            return "Error: command is required for action=start."
        task = await _MANAGER.start(command, cwd=cwd, timeout=timeout, env=env)
        return (
            f"Background task {task.task_id} started.\n"
            f"command={task.command}\n"
            "Use background_task(action='status', task_id='...') to check it."
        )

    if action == "status":
        if not task_id:
            return "Error: task_id is required for action=status."
        task = await _MANAGER.get(task_id)
        if task is None:
            return f"Error: unknown background task {task_id!r}."
        return _render_task(task)

    if action == "list":
        tasks = await _MANAGER.list()
        if not tasks:
            return "No background tasks."
        return "\n\n".join(_render_task(task, output_limit=800) for task in tasks[:20])

    if action == "cancel":
        if not task_id:
            return "Error: task_id is required for action=cancel."
        ok = await _MANAGER.cancel(task_id)
        return f"Cancelled background task {task_id}." if ok else f"Background task {task_id} is not running."

    return "Error: action must be one of start, status, list, cancel."


def _prepare_command(command: list[str] | str, env: dict[str, str] | None) -> _PreparedCommand:
    if isinstance(command, str):
        parts = shlex.split(command)
    else:
        parts = [str(part) for part in command]
    if not parts:
        raise ValueError("command must not be empty")

    merged_env: dict[str, str] | None = None
    if env:
        merged_env = {**os.environ, **{str(k): str(v) for k, v in env.items()}}

    executable = parts[0]
    path_env = (merged_env or os.environ).get("PATH", "")
    resolved = shutil.which(executable, path=path_env)
    if resolved is None and executable in {"python", "python3"} and sys.executable:
        parts = [sys.executable, *parts[1:]]
    return _PreparedCommand(command=parts, env=merged_env)


def _render_task(task: BackgroundTask, output_limit: int = 4000) -> str:
    data = task.to_dict(output_limit=output_limit)
    lines = [
        f"task_id: {data['task_id']}",
        f"status: {data['status']}",
        f"command: {data['command']}",
        f"cwd: {data['cwd']}",
    ]
    if data["exit_code"] is not None:
        lines.append(f"exit_code: {data['exit_code']}")
    if data["output"]:
        lines.append(f"output:\n{data['output']}")
    if data["error"]:
        lines.append(f"stderr/error:\n{data['error']}")
    return "\n".join(lines)

