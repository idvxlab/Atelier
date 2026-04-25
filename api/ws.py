"""
WebSocket endpoint for real-time message streaming.

Clients connect to /ws/{session_id} and receive JSON-encoded messages
as they arrive from the engine.
"""
from __future__ import annotations

import json
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from fastapi.routing import APIRouter

from api.rest import _get_engine, _engines

router = APIRouter()


@router.websocket("/ws/{session_id}")
async def session_websocket(websocket: WebSocket, session_id: str) -> None:
    """
    Stream messages for a session over WebSocket.

    Protocol (server → client):
      {"type": "message", "data": <serialized Message>}
      {"type": "state",   "data": {"state": "RUNNING", "is_running": true}}
      {"type": "error",   "data": {"detail": "..."}}

    Protocol (client → server):
      {"type": "message", "text": "..."}   → send user message
      {"type": "cancel"}                   → cancel running loop
    """
    await websocket.accept()

    if session_id not in _engines:
        await websocket.send_text(
            json.dumps({"type": "error", "data": {"detail": f"Session {session_id!r} not found"}})
        )
        await websocket.close(code=4004)
        return

    engine = _engines[session_id]

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(
                    json.dumps({"type": "error", "data": {"detail": "Invalid JSON"}})
                )
                continue

            msg_type = msg.get("type")

            if msg_type == "message":
                text = msg.get("text", "")
                if text:
                    await engine.send_message(text)
                snapshot = await engine.get_snapshot()
                await websocket.send_text(
                    json.dumps({"type": "state", "data": snapshot})
                )

            elif msg_type == "cancel":
                await engine.cancel()
                await websocket.send_text(
                    json.dumps({"type": "state", "data": {"status": "cancel_requested"}})
                )

            elif msg_type == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))

            else:
                await websocket.send_text(
                    json.dumps({"type": "error", "data": {"detail": f"Unknown message type: {msg_type!r}"}})
                )

    except WebSocketDisconnect:
        pass
