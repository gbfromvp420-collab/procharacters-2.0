"""KGC global policies — defaults for new companion sessions and fleet automation."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_PATH = "data/kgc_policies.json"


@dataclass
class KGCPoliciesState:
    default_relationship_mode: str = ""
    default_system_prompt: str = ""
    auto_prune_enabled: bool = True


class KGCPolicies:
    """In-memory KGC policies with optional JSON persistence."""

    def __init__(self, path: str = _DEFAULT_PATH) -> None:
        self._path = Path(path)
        self._lock = Lock()
        self._state = KGCPoliciesState()
        self._load()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "default_relationship_mode": self._state.default_relationship_mode,
                "default_system_prompt": self._state.default_system_prompt,
                "auto_prune_enabled": self._state.auto_prune_enabled,
            }

    def get_default_relationship_mode(self) -> str:
        with self._lock:
            return self._state.default_relationship_mode

    def get_default_system_prompt(self, fallback: str) -> str:
        with self._lock:
            prompt = self._state.default_system_prompt.strip()
            return prompt if prompt else fallback

    def is_auto_prune_enabled(self) -> bool:
        with self._lock:
            return self._state.auto_prune_enabled

    def update(
        self,
        *,
        default_relationship_mode: str | None = None,
        default_system_prompt: str | None = None,
        auto_prune_enabled: bool | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            if default_relationship_mode is not None:
                self._state.default_relationship_mode = default_relationship_mode
            if default_system_prompt is not None:
                self._state.default_system_prompt = default_system_prompt
            if auto_prune_enabled is not None:
                self._state.auto_prune_enabled = auto_prune_enabled
            self._persist_unlocked()
            return {
                "default_relationship_mode": self._state.default_relationship_mode,
                "default_system_prompt": self._state.default_system_prompt,
                "auto_prune_enabled": self._state.auto_prune_enabled,
            }

    def apply_snapshot(self, data: dict[str, Any]) -> dict[str, Any]:
        """Merge policy fields from a backup payload."""
        return self.update(
            default_relationship_mode=data.get("default_relationship_mode"),
            default_system_prompt=data.get("default_system_prompt"),
            auto_prune_enabled=data.get("auto_prune_enabled"),
        )

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            with self._path.open("r", encoding="utf-8") as fh:
                raw = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to load KGC policies from %s: %s", self._path, exc)
            return
        if not isinstance(raw, dict):
            logger.warning("KGC policies file %s has unexpected shape", self._path)
            return
        with self._lock:
            self._state = KGCPoliciesState(
                default_relationship_mode=str(raw.get("default_relationship_mode", "")),
                default_system_prompt=str(raw.get("default_system_prompt", "")),
                auto_prune_enabled=bool(raw.get("auto_prune_enabled", True)),
            )

    def _persist_unlocked(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "default_relationship_mode": self._state.default_relationship_mode,
            "default_system_prompt": self._state.default_system_prompt,
            "auto_prune_enabled": self._state.auto_prune_enabled,
        }
        fd, tmp_path = tempfile.mkstemp(
            dir=self._path.parent,
            prefix=".kgc_policies.",
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2)
                fh.write("\n")
            os.replace(tmp_path, self._path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise