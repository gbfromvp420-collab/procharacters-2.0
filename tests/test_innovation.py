"""Tests for Innovation lanes (post-v1.0)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.rate_limit import reset_rate_limiter
from app.main import create_app
from app.services.workforce.innovation import InnovationLanes


def _patch_settings(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> None:
    get_settings.cache_clear()
    monkeypatch.setattr("app.core.config.get_settings", lambda: settings)
    monkeypatch.setattr("app.core.lifecycle.get_settings", lambda: settings)


@pytest.fixture
def innovation_client(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[TestClient]:
    settings = Settings(
        llm_provider="mock",
        tts_provider="mock",
        video_provider="mock",
        mock_realistic=False,
        companion_persist_enabled=False,
        api_key_enabled=False,
        rate_limit_enabled=False,
        innovation_lanes_path=str(tmp_path / "innovation_lanes.json"),
        deployment_phase=20,
        app_version="1.0.0",
    )
    _patch_settings(monkeypatch, settings)
    reset_rate_limiter()
    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings.cache_clear()


def test_innovation_status(innovation_client: TestClient) -> None:
    response = innovation_client.get("/api/v1/workforce/innovation")
    assert response.status_code == 200
    body = response.json()
    assert body["innovation_mode"] is True
    assert body["active_lane_id"] == "real_providers"
    assert body["lanes_total"] == 4
    assert body["real_providers_ready"] is False


def test_innovation_lanes_list(innovation_client: TestClient) -> None:
    response = innovation_client.get("/api/v1/workforce/innovation/lanes")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 4
    assert body["active_lane_id"] == "real_providers"
    labels = {lane["label"] for lane in body["lanes"]}
    assert labels == {"Real", "Soul", "$", "Live"}


def test_real_provider_readiness_mock(innovation_client: TestClient) -> None:
    response = innovation_client.get("/api/v1/workforce/innovation/real")
    assert response.status_code == 200
    body = response.json()
    assert body["lane_id"] == "real_providers"
    assert body["all_real_ready"] is False
    assert len(body["providers"]) == 3
    assert len(body["env_checklist"]) >= 6
    assert len(body["activation_steps"]) >= 5
    assert body["providers"][0]["next_step"]


def test_innovation_service_all_real_ready(tmp_path: Path) -> None:
    settings = Settings(
        llm_provider="openai_compatible",
        llm_base_url="https://abc123-8000.proxy.runpod.net/v1",
        tts_provider="http",
        tts_base_url="https://abc123-8002.proxy.runpod.net",
        video_provider="http",
        video_base_url="https://abc123-8003.proxy.runpod.net",
    )
    innovation = InnovationLanes(schema_path=str(tmp_path / "lanes.json"))
    report = innovation.build_real_provider_readiness(settings=settings)
    assert report["all_real_ready"] is True
    assert report["configured_providers"] == 3