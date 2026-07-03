"""Tests for Continuity Forge layer (Phase 10)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.rate_limit import reset_rate_limiter
from app.main import create_app


def _patch_settings(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> None:
    get_settings.cache_clear()
    monkeypatch.setattr("app.core.config.get_settings", lambda: settings)
    monkeypatch.setattr("app.core.lifecycle.get_settings", lambda: settings)


@pytest.fixture
def continuity_client(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[TestClient]:
    settings = Settings(
        llm_provider="mock",
        tts_provider="mock",
        video_provider="mock",
        mock_realistic=False,
        companion_persist_enabled=True,
        companion_persist_path=str(tmp_path / "companion_sessions.json"),
        api_key_enabled=False,
        rate_limit_enabled=False,
    )
    _patch_settings(monkeypatch, settings)
    reset_rate_limiter()
    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings.cache_clear()


def test_webrtc_restore_rehydrates_persisted_companion(continuity_client: TestClient) -> None:
    session_id = "phase10-continuity-session"
    assert continuity_client.patch(
        f"/api/v1/companion/{session_id}/config",
        json={"voice": "bright"},
    ).status_code == 200

    assert continuity_client.get("/api/v1/webrtc/sessions").json()["count"] == 0

    restored = continuity_client.post(f"/api/v1/webrtc/session/{session_id}/restore")
    assert restored.status_code == 200
    assert restored.json()["session_id"] == session_id

    listed = continuity_client.get("/api/v1/webrtc/sessions")
    assert listed.status_code == 200
    assert session_id in listed.json()["sessions"]