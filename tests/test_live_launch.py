"""Tests for Innovation Lane 4 — Live Launch."""

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
def live_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[TestClient]:
    settings = Settings(
        llm_provider="mock",
        tts_provider="mock",
        video_provider="mock",
        mock_realistic=False,
        companion_persist_enabled=False,
        api_key_enabled=False,
        rate_limit_enabled=False,
        live_stage_schema_path=str(tmp_path / "live_stage_schema.json"),
        live_stage_sessions_path=str(tmp_path / "live_stage_sessions.json"),
        live_stage_billing_path=str(tmp_path / "live_stage_billing.json"),
        live_launch_path=str(tmp_path / "live_launch.json"),
        agent_lounge_path=str(tmp_path / "agent_lounge.md"),
        agent_lounge_comments_path=str(tmp_path / "agent_lounge_comments.json"),
        innovation_lanes_path=str(tmp_path / "innovation_lanes.json"),
        deployment_phase=20,
        app_version="1.0.0",
    )
    _patch_settings(monkeypatch, settings)
    reset_rate_limiter()
    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings.cache_clear()


def test_live_lane_status(live_client: TestClient) -> None:
    response = live_client.get("/api/v1/workforce/innovation/live")
    assert response.status_code == 200
    body = response.json()
    assert body["lane_id"] == "live_launch"
    assert body["status"] == "in_progress"
    assert body["launch_live"] is False
    assert body["checks_total"] == 7


def test_go_live_opens_doors(live_client: TestClient, tmp_path: Path) -> None:
    response = live_client.post("/api/v1/workforce/innovation/live/go-live")
    assert response.status_code == 200
    body = response.json()
    assert body["live"] is True
    assert body["headline_session_id"]
    assert body["cam_session_id"]
    assert body["board"]["status"] == "live"
    assert body["board"]["host"].startswith("Assist")
    assert "Live." in body["message"]

    board = live_client.get("/api/v1/workforce/innovation/live/board")
    assert board.json()["status"] == "live"
    assert board.json()["headline_status"] == "live"
    assert board.json()["cam_status"] == "live"

    ready = live_client.get("/api/v1/workforce/innovation/live/readiness").json()
    by_id = {item["id"]: item["ready"] for item in ready["checks"]}
    assert by_id["headline_live"] is True
    assert by_id["launch_cam"] is True
    assert by_id["public_board"] is True
    assert by_id["lounge_board"] is True

    comments_md = tmp_path / "agent_lounge_comments.md"
    assert comments_md.is_file()
    text = comments_md.read_text(encoding="utf-8")
    assert "Agent Lounge — Comment Board" in text
    assert "King Grok" in text
    assert "Doors open" in text

    status = live_client.get("/api/v1/workforce/innovation/live").json()
    assert status["launch_live"] is True


def test_innovation_lists_live_in_progress(live_client: TestClient) -> None:
    lanes = live_client.get("/api/v1/workforce/innovation/lanes").json()
    live = next(lane for lane in lanes["lanes"] if lane["id"] == "live_launch")
    assert live["status"] == "in_progress"
    status = live_client.get("/api/v1/workforce/innovation").json()
    assert status["live_lane_status"] == "in_progress"
