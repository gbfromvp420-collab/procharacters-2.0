"""In-memory request and session counters for lightweight observability."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field


@dataclass
class MetricsCollector:
    """Thread-safe in-memory counters for API and companion activity."""

    perform_requests: int = 0
    speak_requests: int = 0
    tokens_streamed: int = 0
    sessions_created: int = 0
    sessions_closed: int = 0
    companion_turns_saved: int = 0
    bond_increments: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def increment_perform_requests(self, count: int = 1) -> None:
        with self._lock:
            self.perform_requests += count

    def increment_speak_requests(self, count: int = 1) -> None:
        with self._lock:
            self.speak_requests += count

    def increment_tokens_streamed(self, count: int = 1) -> None:
        with self._lock:
            self.tokens_streamed += count

    def increment_sessions_created(self, count: int = 1) -> None:
        with self._lock:
            self.sessions_created += count

    def increment_sessions_closed(self, count: int = 1) -> None:
        with self._lock:
            self.sessions_closed += count

    def increment_companion_turns_saved(self, count: int = 1) -> None:
        with self._lock:
            self.companion_turns_saved += count

    def increment_bond_increments(self, count: int = 1) -> None:
        with self._lock:
            self.bond_increments += count

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return {
                "perform_requests": self.perform_requests,
                "speak_requests": self.speak_requests,
                "tokens_streamed": self.tokens_streamed,
                "sessions_created": self.sessions_created,
                "sessions_closed": self.sessions_closed,
                "companion_turns_saved": self.companion_turns_saved,
                "bond_increments": self.bond_increments,
            }

    def metrics_summary(self) -> dict[str, int]:
        """Compact counter snapshot for /health and ops dashboards."""
        return self.snapshot()