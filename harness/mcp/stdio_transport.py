"""Stdio transport for MCP (Model Context Protocol).

Launches an MCP Server as a child process and communicates via
newline-delimited JSON-RPC 2.0 messages over stdin/stdout.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import subprocess
from typing import Any

logger = logging.getLogger(__name__)


class TransportError(Exception):
    """Raised when the underlying subprocess fails or returns unexpected data."""


class StdioTransport:
    """Manages a single MCP Server child process via stdin/stdout JSON-RPC."""

    def __init__(self) -> None:
        self._process: asyncio.subprocess.Process | None = None
        self._sync_process: subprocess.Popen[bytes] | None = None
        self._lock = asyncio.Lock()
        self._next_id = 1

    async def start(self, command: list[str]) -> None:
        """Start the MCP Server subprocess."""
        if self._process is not None or self._sync_process is not None:
            raise TransportError("Transport already started; call close() first.")
        if not command:
            raise TransportError("Empty command; cannot start MCP Server.")

        spawn_mode, spawn_target = _prepare_subprocess_command(command)
        try:
            if spawn_mode == "shell":
                self._process = await asyncio.create_subprocess_shell(
                    spawn_target,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            else:
                self._process = await asyncio.create_subprocess_exec(
                    *spawn_target,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
        except NotImplementedError:
            self._sync_process = _start_sync_subprocess(spawn_mode, spawn_target)

        pid = self._process.pid if self._process is not None else self._sync_process.pid
        logger.debug("MCP Server started (pid=%s): %s", pid, command)

        await asyncio.sleep(0.35 if os.name == "nt" else 0.1)
        returncode = self._get_returncode()
        if returncode is not None:
            stderr_text = await self._read_stderr_sample()
            raise TransportError(
                f"MCP Server exited during startup with code {returncode}. "
                f"stderr: {stderr_text}"
            )

    async def close(self) -> None:
        """Terminate the subprocess and release resources."""
        if self._process is None and self._sync_process is None:
            return

        if self._process is not None:
            proc = self._process
            try:
                proc.terminate()
                await asyncio.wait_for(proc.wait(), timeout=5.0)
            except (ProcessLookupError, asyncio.TimeoutError):
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
                try:
                    await asyncio.wait_for(proc.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    pass
            finally:
                try:
                    if proc.stdin:
                        proc.stdin.close()
                        wait_closed = getattr(proc.stdin, "wait_closed", None)
                        if callable(wait_closed):
                            await wait_closed()
                except Exception:
                    pass
                try:
                    await asyncio.wait_for(proc.communicate(), timeout=1.0)
                except Exception:
                    pass
                self._process = None

        if self._sync_process is not None:
            proc = self._sync_process
            try:
                proc.terminate()
                await asyncio.to_thread(proc.wait, 5.0)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
                try:
                    await asyncio.to_thread(proc.wait, 5.0)
                except Exception:
                    pass
            finally:
                for stream in (proc.stdin, proc.stdout, proc.stderr):
                    try:
                        if stream:
                            stream.close()
                    except Exception:
                        pass
                self._sync_process = None

        logger.debug("MCP Server process terminated.")

    async def send(self, msg: dict[str, Any]) -> dict[str, Any]:
        """Send a JSON-RPC request and wait for the matching response."""
        if self._process is None and self._sync_process is None:
            raise TransportError("Transport not started; call start() first.")
        async with self._lock:
            await self._write(msg)
            return await self._read_response(msg["id"])

    async def notify(self, msg: dict[str, Any]) -> None:
        """Send a JSON-RPC notification (no response expected)."""
        if self._process is None and self._sync_process is None:
            raise TransportError("Transport not started; call start() first.")
        async with self._lock:
            await self._write(msg)

    async def _write(self, msg: dict[str, Any]) -> None:
        line = json.dumps(msg, ensure_ascii=False) + "\n"
        data = line.encode()
        if self._process is not None:
            assert self._process.stdin is not None
            self._process.stdin.write(data)
            await self._process.stdin.drain()
        else:
            assert self._sync_process is not None and self._sync_process.stdin is not None
            await asyncio.to_thread(self._sync_process.stdin.write, data)
            await asyncio.to_thread(self._sync_process.stdin.flush)
        logger.debug("MCP -> server: %s", line.rstrip())

    async def _read_response(self, expected_id: int) -> dict[str, Any]:
        while True:
            try:
                raw = await self._read_stdout_line()
            except asyncio.TimeoutError as exc:
                raise TransportError("Timeout waiting for MCP Server response.") from exc

            if not raw:
                stderr_text = await self._read_stderr_sample()
                raise TransportError(
                    f"MCP Server process exited unexpectedly. stderr: {stderr_text}"
                )

            line = raw.decode(errors="replace").strip()
            if not line:
                continue

            logger.debug("MCP <- server: %s", line)
            try:
                response = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("Non-JSON line from MCP Server (skipped): %s", line)
                continue

            if response.get("id") == expected_id:
                return response

    async def _read_stdout_line(self) -> bytes:
        if self._process is not None:
            assert self._process.stdout is not None
            return await asyncio.wait_for(self._process.stdout.readline(), timeout=120.0)

        assert self._sync_process is not None and self._sync_process.stdout is not None
        return await asyncio.wait_for(
            asyncio.to_thread(self._sync_process.stdout.readline),
            timeout=120.0,
        )

    async def _read_stderr_sample(self) -> str:
        if self._process is not None and self._process.stderr is not None:
            try:
                data = await asyncio.wait_for(self._process.stderr.read(4096), timeout=2.0)
                return data.decode(errors="replace")
            except asyncio.TimeoutError:
                return ""

        if self._sync_process is not None and self._sync_process.stderr is not None:
            try:
                data = await asyncio.wait_for(
                    asyncio.to_thread(self._sync_process.stderr.read, 4096),
                    timeout=2.0,
                )
                return data.decode(errors="replace")
            except asyncio.TimeoutError:
                return ""

        return ""

    def _get_returncode(self) -> int | None:
        if self._process is not None:
            return self._process.returncode
        if self._sync_process is not None:
            return self._sync_process.poll()
        return None

    def next_id(self) -> int:
        """Return a monotonically increasing request ID."""
        rid = self._next_id
        self._next_id += 1
        return rid


def _start_sync_subprocess(
    spawn_mode: str,
    spawn_target: list[str] | str,
) -> subprocess.Popen[bytes]:
    if spawn_mode == "shell":
        return subprocess.Popen(
            spawn_target,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
        )
    return subprocess.Popen(
        spawn_target,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
    )


def _prepare_subprocess_command(command: list[str]) -> tuple[str, list[str] | str]:
    """
    Prepare a subprocess target that works reliably across platforms.

    On Windows, `npx` and similar launchers usually resolve to `.cmd`/`.bat`
    files. Those should be executed through `cmd.exe /c` rather than passed
    directly to `create_subprocess_exec()`.
    """
    exe = command[0]
    resolved = shutil.which(exe)
    if not resolved and os.name == "nt":
        for cand in (f"{exe}.cmd", f"{exe}.exe", f"{exe}.bat"):
            resolved = shutil.which(cand)
            if resolved:
                break

    resolved = resolved or exe
    final_command = [resolved, *command[1:]]

    if os.name == "nt" and resolved.lower().endswith((".cmd", ".bat")):
        comspec = os.environ.get("COMSPEC", "cmd.exe")
        cmdline = subprocess.list2cmdline(final_command)
        return "exec", [comspec, "/d", "/s", "/c", cmdline]

    return "exec", final_command
