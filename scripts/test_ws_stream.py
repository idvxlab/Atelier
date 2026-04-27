#!/usr/bin/env python
"""
Standalone WebSocket streaming smoke-test.

Usage (server must be running first):
    uvicorn api.rest:app --reload --port 8000
    python scripts/test_ws_stream.py [--url http://localhost:8000] [--message "hello"]

Prints every frame received from the server, highlighting token frames.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time


async def run(base_url: str, message: str) -> None:
    try:
        import httpx
        import websockets
    except ImportError:
        print("Missing dependencies. Run: pip install httpx websockets", file=sys.stderr)
        sys.exit(1)

    ws_url = base_url.replace("http://", "ws://").replace("https://", "wss://")

    # ── 1. Create session ───────────────────────────────────────────────
    print(f"[test] POST {base_url}/sessions ...")
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{base_url}/sessions",
            json={"provider": "", "persona": ""},
            timeout=10,
        )
    if resp.status_code != 201:
        print(f"[test] ERROR creating session: {resp.status_code} {resp.text}")
        sys.exit(1)

    session = resp.json()
    session_id = session["session_id"]
    print(f"[test] Session created: {session_id}")

    # ── 2. Connect WebSocket ────────────────────────────────────────────
    ws_endpoint = f"{ws_url}/ws/{session_id}"
    print(f"[test] Connecting WS: {ws_endpoint}")

    async with websockets.connect(ws_endpoint) as ws:
        print(f"[test] Connected. Sending message: {message!r}")

        # Send user message
        await ws.send(json.dumps({"type": "message", "text": message}))

        # ── 3. Receive frames until engine is done ──────────────────────
        token_count = 0
        t0 = time.monotonic()

        while True:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=30)
            except asyncio.TimeoutError:
                print("[test] TIMEOUT — no frame received for 30s")
                break

            frame = json.loads(raw)
            ftype = frame.get("type")
            elapsed = time.monotonic() - t0

            if ftype == "token":
                token_count += 1
                tok = frame["data"]
                print(f"  [{elapsed:.2f}s] TOKEN #{token_count}: {tok!r}")

            elif ftype == "message":
                role = frame["data"].get("role", "?")
                blocks = frame["data"].get("content", [])
                text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
                print(f"  [{elapsed:.2f}s] MESSAGE role={role}: {text[:120]!r}")

            elif ftype == "state":
                state = frame["data"].get("state", "?")
                is_running = frame["data"].get("is_running", "?")
                print(f"  [{elapsed:.2f}s] STATE: {state}, is_running={is_running}")
                if state in ("COMPLETED", "ERROR", "WAITING_INPUT") and not is_running:
                    print(f"[test] Engine stopped. {token_count} tokens received.")
                    break

            elif ftype == "error":
                print(f"  [{elapsed:.2f}s] ERROR: {frame['data']}")
                break

            else:
                print(f"  [{elapsed:.2f}s] UNKNOWN frame: {frame}")

    print("[test] Done.")


def main() -> None:
    parser = argparse.ArgumentParser(description="WebSocket streaming smoke-test")
    parser.add_argument("--url", default="http://localhost:8000", help="Server base URL")
    parser.add_argument("--message", default="Say 'hello world' exactly.", help="Message to send")
    args = parser.parse_args()

    asyncio.run(run(args.url, args.message))


if __name__ == "__main__":
    main()
