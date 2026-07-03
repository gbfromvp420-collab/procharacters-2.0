"""JSON file persistence for companion session metadata and conversation history."""

import json
import logging
import os
import tempfile
from pathlib import Path
from threading import Lock

logger = logging.getLogger(__name__)


class CompanionPersistence:
    """Load/save companion sessions to a JSON file with atomic writes."""

    def __init__(self, path: str) -> None:
        self._path = Path(path)
        self._lock = Lock()

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> dict[str, dict]:
        """Load all sessions from disk. Returns empty dict if file is missing or invalid."""
        if not self._path.exists():
            return {}
        try:
            with self._path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning(
                "Failed to load companion sessions from %s: %s",
                self._path,
                exc,
            )
            return {}
        if not isinstance(data, dict):
            logger.warning(
                "Companion sessions file %s has unexpected shape; starting empty",
                self._path,
            )
            return {}
        return data

    def save(self, sessions: dict[str, dict]) -> None:
        """Atomically write sessions to disk (temp file + rename)."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            fd, tmp_path = tempfile.mkstemp(
                dir=self._path.parent,
                prefix=".companion_sessions.",
                suffix=".tmp",
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    json.dump(sessions, fh, indent=2)
                    fh.write("\n")
                os.replace(tmp_path, self._path)
            except Exception:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise