"""KGC audit log — in-memory ring buffer for executive actions."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class AuditEntry:
    timestamp: str
    action: str
    actor: str
    detail: str
    result: str


class AuditLog:
    """Thread-safe ring buffer of recent KGC actions (max 200 entries)."""

    def __init__(self, *, max_entries: int = 200) -> None:
        self._max_entries = max_entries
        self._entries: deque[AuditEntry] = deque(maxlen=max_entries)
        self._lock = Lock()

    def log_action(
        self,
        action: str,
        detail: str,
        *,
        result: str = "ok",
        actor: str = "ceo",
    ) -> AuditEntry:
        entry = AuditEntry(
            timestamp=_utc_now_iso(),
            action=action,
            actor=actor,
            detail=detail,
            result=result,
        )
        with self._lock:
            self._entries.append(entry)
        return entry

    def get_entries(self, *, limit: int = 50) -> list[AuditEntry]:
        if limit <= 0:
            return []
        with self._lock:
            items = list(self._entries)
        return items[-limit:][::-1]

    def tail(self, *, limit: int = 50) -> list[dict[str, str]]:
        return [
            {
                "timestamp": entry.timestamp,
                "action": entry.action,
                "actor": entry.actor,
                "detail": entry.detail,
                "result": entry.result,
            }
            for entry in self.get_entries(limit=limit)
        ]


_audit_log = AuditLog()


def get_audit_log() -> AuditLog:
    return _audit_log


def log_action(action: str, detail: str, result: str = "ok", actor: str = "ceo") -> AuditEntry:
    """Record a KGC executive action in the global audit ring buffer."""
    return _audit_log.log_action(action, detail, result=result, actor=actor)