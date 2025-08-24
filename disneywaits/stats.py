from __future__ import annotations

import statistics
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Deque, List, Tuple


@dataclass
class WaitEntry:
    timestamp: datetime
    wait: int


class RideStats:
    """Track wait time statistics for a single ride."""

    def __init__(self) -> None:
        self.history: Deque[WaitEntry] = deque()
        self.current_wait: int | None = None
        self.is_open: bool = True

    def add_wait(self, wait: int, timestamp: datetime | None = None) -> None:
        """Add a wait time sample.

        Only stores samples from the last five days.
        """
        timestamp = timestamp or datetime.now(UTC)
        self.current_wait = wait
        self.history.append(WaitEntry(timestamp, wait))
        self._trim_history(timestamp)

    def mark_closed(self) -> None:
        self.is_open = False
        self.current_wait = None

    def mark_open(self) -> None:
        self.is_open = True

    def _trim_history(self, now: datetime) -> None:
        cutoff = now - timedelta(days=5)
        while self.history and self.history[0].timestamp < cutoff:
            self.history.popleft()

    def mean(self) -> float | None:
        if not self.history:
            return None
        return statistics.mean(entry.wait for entry in self.history)

    def stdev(self) -> float | None:
        if len(self.history) < 2:
            return None
        return statistics.stdev(entry.wait for entry in self.history)

    def is_unusually_low(self) -> bool:
        """Return True if current wait is >1 std dev below mean."""
        if self.current_wait is None:
            return False
        mean = self.mean()
        stdev = self.stdev()
        if mean is None or stdev is None or stdev == 0:
            return False
        return self.current_wait < mean - stdev

