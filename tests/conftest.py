"""Shared pytest fixtures — isolate on-disk state for API integration tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import Settings, get_settings


@pytest.fixture(autouse=True)
def isolated_app_data_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep companion sessions and KGC policies off repo data/ during tests."""
    settings = Settings(
        companion_persist_enabled=True,
        companion_persist_path=str(tmp_path / "companion_sessions.json"),
        kgc_policies_path=str(tmp_path / "kgc_policies.json"),
    )
    get_settings.cache_clear()
    monkeypatch.setattr("app.core.config.get_settings", lambda: settings)
    monkeypatch.setattr("app.core.lifecycle.get_settings", lambda: settings)
    yield
    get_settings.cache_clear()