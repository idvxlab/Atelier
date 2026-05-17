"""
WebSocket endpoint for real-time message streaming.

Clients connect to /ws/{session_id} and receive JSON-encoded messages
as they arrive from the engine.
"""
from __future__ import annotations

import json

from fastapi import WebSocket, WebSocketDisconnect
from fastapi.routing import APIRouter

from api.rest import _get_engine, _engines
from harness.engine.engine import serialize_message
from harness.types.messages import Message

router = APIRouter()

_THINKING_START = "\x00THINKING\x00"
_THINKING_TOKEN_PREFIX = "\x00THINKING_TOKEN\x00"


@router.websocket("/ws/{session_id}")
async def session_websocket(websocket: WebSocket, session_id: str) -> None:
    """
    Stream messages for a session over WebSocket.

    Protocol (server → client):
      {"type": "token",          "data": "<text chunk>"}        ← streamed text tokens
      {"type": "thinking"}                                       ← thinking phase started
      {"type": "thinking_token", "data": "<thinking chunk>"}    ← streamed thinking tokens
      {"type": "message",        "data": <serialized Message>}  ← full message on completion
      {"type": "state",          "data": <snapshot>}            ← state change or ping response
      {"type": "error",          "data": {"detail": "..."}}

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

    async def push_message(msg: Message) -> None:
        """Fires for every completed message (assistant reply or tool result)."""
        await websocket.send_text(
            json.dumps({"type": "message", "data": serialize_message(msg)})
        )

    async def push_token(text: str) -> None:
        """Fires for each streamed token or sentinel."""
        if text == _THINKING_START:
            await websocket.send_text(json.dumps({"type": "thinking"}))
        elif text.startswith(_THINKING_TOKEN_PREFIX):
            chunk = text[len(_THINKING_TOKEN_PREFIX):]
            await websocket.send_text(
                json.dumps({"type": "thinking_token", "data": chunk})
            )
        else:
            await websocket.send_text(
                json.dumps({"type": "token", "data": text})
            )

    async def push_state() -> None:
        """Fires when engine state changes (RUNNING → COMPLETED/ERROR/WAITING_INPUT)."""
        snapshot = await engine.get_snapshot()
        await websocket.send_text(
            json.dumps({"type": "state", "data": snapshot})
        )

    engine.add_message_listener(push_message)
    engine.add_token_listener(push_token)
    engine.add_state_listener(push_state)
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

            elif msg_type == "confirm":
                await engine.confirm()
                snapshot = await engine.get_snapshot()
                await websocket.send_text(json.dumps({"type": "state", "data": snapshot}))

            elif msg_type == "deny":
                await engine.deny()
                snapshot = await engine.get_snapshot()
                await websocket.send_text(json.dumps({"type": "state", "data": snapshot}))

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
    finally:
        engine.remove_message_listener(push_message)
        engine.remove_token_listener(push_token)
        engine.remove_state_listener(push_state)
