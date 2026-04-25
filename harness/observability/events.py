"""
Structured observability for the agent harness.

Embed calls at DECISION POINTS — where the code decides whether to act —
not at execution points. The four states cover every outcome:

  triggered-executed    — the guard fired and the action ran normally
  condition-not-met     — the guard checked but condition was false
  triggered-intercepted — the guard fired but the action was blocked
  execution-error       — the action ran but raised an exception

A missing event is the most dangerous signal: it means the code path
was never reached at all.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from harness.types.events import EventState, ObservabilityEvent

logger = logging.getLogger("harness.events")


class EventEmitter:
    def __init__(self, session_id: str) -> None:
        self._session_id = session_id
        self._round = 0

    def set_round(self, round_idx: int) -> None:
        self._round = round_idx

    def emit(
        self,
        event_type: str,
        state: EventState,
        detail: dict[str, Any] | None = None,
    ) -> None:
        event = ObservabilityEvent(
            event_type=event_type,
            state=state,
            session_id=self._session_id,
            round_index=self._round,
            detail=detail or {},
        )
        logger.info(
            json.dumps(
                {
                    "event_type": event.event_type,
                    "state": event.state,
                    "session_id": event.session_id,
                    "round": event.round_index,
                    "timestamp": event.timestamp,
                    **event.detail,
                }
            )
        )

    def emit_error(
        self,
        event_type: str,
        error: str,
        round_idx: int | None = None,
    ) -> None:
        self.emit(
            event_type,
            "execution-error",
            detail={"error": error, "round": round_idx if round_idx is not None else self._round},
        )
