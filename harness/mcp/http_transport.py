"""HTTP transport for MCP (Model Context Protocol).

Sends JSON-RPC 2.0 messages to a remote MCP endpoint over HTTP POST.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from harness.mcp.stdio_transport import TransportError

logger = logging.getLogger(__name__)


class HttpTransport:
    """Manages a single remote MCP endpoint over HTTP."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self._url: str = ""
        self._next_id: int = 1

    async def start(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        timeout: float = 30.0,
    ) -> None:
        if self._client is not None:
            raise TransportError("Transport already started; call close() first.")
        if not url:
            raise TransportError("Empty URL; cannot start HTTP MCP transport.")

        self._url = url
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=min(timeout, 10.0)),
            headers=headers or {},
        )
        logger.debug("MCP HTTP transport started: %s", url)

    async def close(self) -> None:
        if self._client is None:
            return
        await self._client.aclose()
        self._client = None
        logger.debug("MCP HTTP transport closed: %s", self._url)

    async def send(self, msg: dict[str, Any]) -> dict[str, Any]:
        if self._client is None:
            raise TransportError("Transport not started; call start() first.")

        try:
            response = await self._client.post(self._url, json=msg)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise TransportError(f"HTTP MCP request failed: {exc}") from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise TransportError("HTTP MCP endpoint returned non-JSON response.") from exc

        if not isinstance(data, dict):
            raise TransportError("HTTP MCP endpoint returned invalid JSON-RPC payload.")
        return data

    async def notify(self, msg: dict[str, Any]) -> None:
        if self._client is None:
            raise TransportError("Transport not started; call start() first.")

        try:
            response = await self._client.post(self._url, json=msg)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise TransportError(f"HTTP MCP notification failed: {exc}") from exc

    def next_id(self) -> int:
        rid = self._next_id
        self._next_id += 1
        return rid
