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
from typing import Any

logger = logging.getLogger(__name__)


class TransportError(Exception):
    """Raised when the underlying subprocess fails or returns unexpected data."""


class StdioTransport:
    """Manages a single MCP Server child process via stdin/stdout JSON-RPC."""

    def __init__(self) -> None:
        self._process: asyncio.subprocess.Process | None = None
        self._lock = asyncio.Lock()
        self._next_id: int = 1

    # ── Lifecycle ────────────────────────────────────────────────────────────

    async def start(self, command: list[str]) -> None:
        """Start the MCP Server subprocess.

        Args:
            command: Executable + arguments, e.g.
                     ["npx", "-y", "@modelcontextprotocol/server-filesystem", "."]
        """
        if self._process is not None:
            raise TransportError("Transport already started; call close() first.")

        if not command:
            raise TransportError("Empty command; cannot start MCP Server.")

        # On Windows, executables like `npx` are typically `npx.cmd`.
        # Resolve via PATH so asyncio can spawn correctly.
        exe = command[0]
        resolved = shutil.which(exe)
        if not resolved and os.name == "nt":
            for cand in (f"{exe}.cmd", f"{exe}.exe", f"{exe}.bat"):
                resolved = shutil.which(cand)
                if resolved:
                    break
        if resolved:
            command = [resolved, *command[1:]]

        self._process = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        logger.debug("MCP Server started (pid=%s): %s", self._process.pid, command)

    async def close(self) -> None:
        """Terminate the subprocess and release resources."""
        if self._process is None:
            return
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
            # Best-effort: close stdin and drain/close underlying transports to
            # avoid Windows Proactor "unclosed transport" warnings.
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
            logger.debug("MCP Server process terminated.")

    # ── Messaging ────────────────────────────────────────────────────────────

    async def send(self, msg: dict[str, Any]) -> dict[str, Any]:
        """Send a JSON-RPC request and wait for the matching response.

        The message must already have a valid "id" field so we can
        correlate the response.  Use ``_next_request_id()`` to generate one.

        Args:
            msg: Complete JSON-RPC 2.0 request object (must include "id").

        Returns:
            The JSON-RPC response dict (may contain "result" or "error").

        Raises:
            TransportError: If the process has not been started, dies, or
                            returns malformed data.
        """
        if self._process is None:
            raise TransportError("Transport not started; call start() first.")

        async with self._lock:
            await self._write(msg)
            return await self._read_response(msg["id"])

    async def _write(self, msg: dict[str, Any]) -> None:
        assert self._process and self._process.stdin
        line = json.dumps(msg, ensure_ascii=False) + "\n"
        self._process.stdin.write(line.encode())
        await self._process.stdin.drain()
        logger.debug("MCP → server: %s", line.rstrip())

    async def _read_response(self, expected_id: int) -> dict[str, Any]:
        """Read lines from stdout until we receive the response for *expected_id*."""
        assert self._process and self._process.stdout

        while True:
            try:
                raw = await asyncio.wait_for(
                    # First-time `npx -y ...` may spend time downloading packages.
                    self._process.stdout.readline(), timeout=120.0
                )
            except asyncio.TimeoutError as exc:
                raise TransportError("Timeout waiting for MCP Server response.") from exc

            if not raw:
                # EOF — process likely died
                stderr_bytes = b""
                if self._process.stderr:
                    try:
                        stderr_bytes = await asyncio.wait_for(
                            self._process.stderr.read(4096), timeout=2.0
                        )
                    except asyncio.TimeoutError:
                        pass
                raise TransportError(
                    f"MCP Server process exited unexpectedly. "
                    f"stderr: {stderr_bytes.decode(errors='replace')}"
                )

            line = raw.decode(errors="replace").strip()
            if not line:
                continue

            logger.debug("MCP ← server: %s", line)

            try:
                response = json.loads(line)
            except json.JSONDecodeError as exc:
                logger.warning("Non-JSON line from MCP Server (skipped): %s", line)
                continue

            # Skip notifications (no "id") and mismatched ids
            if response.get("id") == expected_id:
                return response

    # ── Helpers ──────────────────────────────────────────────────────────────

    def next_id(self) -> int:
        """Return a monotonically increasing request ID."""
        rid = self._next_id
        self._next_id += 1
        return rid
