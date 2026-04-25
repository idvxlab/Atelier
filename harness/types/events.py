from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal


EventState = Literal[
    "triggered-executed",    # Decision point fired and ran normally
    "condition-not-met",     # Guard checked, condition was false — did not run
    "triggered-intercepted", # Fired but was blocked / redirected
    "execution-error",       # Fired but failed during execution
]


@dataclass
class ObservabilityEvent:
    event_type: str        # e.g. "tool_call", "loop_detected", "state_transition"
    state: EventState
    session_id: str
    round_index: int
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    detail: dict[str, Any] = field(default_factory=dict)
