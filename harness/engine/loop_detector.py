from __future__ import annotations

import hashlib
import json
from collections import deque

from harness.types.messages import ToolCallBlock


class LoopDetector:
    """
    Detects when the same set of tool calls appears `threshold` times
    within the last `window` rounds.

    Uses a SHA-1 fingerprint of (sorted tool names + sorted inputs)
    so that call order within a round doesn't matter.
    """

    def __init__(self, window: int = 5, threshold: int = 2) -> None:
        self._window = window
        self._threshold = threshold
        self._history: deque[str] = deque(maxlen=window)

    def is_repeated(self, calls: list[ToolCallBlock]) -> bool:
        """
        Return True if this exact call pattern has been seen >= threshold times
        recently. Records the current call regardless.
        """
        key = _fingerprint(calls)
        count = self._history.count(key)
        self._history.append(key)
        # count is before appending; threshold-1 previous occurrences means
        # this call is the threshold-th occurrence.
        return count >= self._threshold - 1

    def reset(self) -> None:
        self._history.clear()


def _fingerprint(calls: list[ToolCallBlock]) -> str:
    parts = sorted(
        f"{c.tool_name}:{json.dumps(c.tool_input, sort_keys=True)}"
        for c in calls
    )
    return hashlib.sha1("|".join(parts).encode()).hexdigest()
