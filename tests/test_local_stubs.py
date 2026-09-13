"""Stage 1 local HTTP contract stubs — finish Lane 1 without RunPod."""

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
def stage1_client(
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
        runpod_wiring_path=str(tmp_path / "runpod_wiring.json"),
        innovation_lanes_path=str(tmp_path / "innovation_lanes.json"),
        deployment_phase=20,
        app_version="1.0.0",
    )
    _patch_settings(monkeypatch, settings)
    reset_rate_limiter()
    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings.cache_clear()


def test_local_stub_health_lists_urls(stage1_client: TestClient) -> None:
    response = stage1_client.get("/api/v1/providers/local")
    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["llm_base_url"].endswith("/api/v1/providers/local/v1")
    assert body["tts_base_url"].endswith("/api/v1/providers/local")
    assert "runpod.io/console/pods" in body["runpod_console"]


def test_local_stub_openai_models(stage1_client: TestClient) -> None:
    response = stage1_client.get("/api/v1/providers/local/v1/models")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data[0]["object"] == "model"


def test_local_stub_chat_completions_stream(stage1_client: TestClient) -> None:
    response = stage1_client.post(
        "/api/v1/providers/local/v1/chat/completions",
        json={
            "messages": [{"role": "user", "content": "Stage 1"}],
            "stream": True,
            "max_tokens": 8,
        },
    )
    assert response.status_code == 200
    text = response.text
    assert "data:" in text
    assert "[DONE]" in text


def test_local_stub_synthesize_and_generate(stage1_client: TestClient) -> None:
    tts = stage1_client.post(
        "/api/v1/providers/local/synthesize",
        json={"text": "Hello stage one", "voice": "default"},
    )
    assert tts.status_code == 200
    audio = tts.json()
    assert audio["audio_b64"]
    assert audio["sample_rate"] == 24000

    video = stage1_client.post(
        "/api/v1/providers/local/generate",
        json={
            "audio_b64": audio["audio_b64"],
            "duration_ms": 200,
            "avatar_id": "default",
            "fps": 25,
        },
    )
    assert video.status_code == 200
    body = video.json()
    assert len(body["frames"]) >= 1
    assert body["frames"][0]["frame_b64"]


def test_advance_blocked_until_stage1_ready(stage1_client: TestClient) -> None:
    blocked = stage1_client.post("/api/v1/workforce/innovation/advance")
    assert blocked.status_code == 409
    detail = blocked.json()["detail"]
    assert "Stage 1" in detail


def test_wire_local_completes_stage1_and_advances(stage1_client: TestClient) -> None:
    wired = stage1_client.post("/api/v1/workforce/innovation/wire/local")
    assert wired.status_code == 200
    body = wired.json()
    assert body["wired"] is True
    assert body["pipelines_activated"] is True
    assert body["stage1_status"] == "ready_local"
    assert body["stage1_source"] == "local_stubs"
    assert body["effective_providers"]["llm"] == "openai_compatible"

    status = stage1_client.get("/api/v1/workforce/innovation")
    assert status.status_code == 200
    snap = status.json()
    assert snap["real_providers_ready"] is True
    assert snap["stage1_status"] == "ready_local"
    assert snap["active_lane_id"] == "real_providers"

    lanes = stage1_client.get("/api/v1/workforce/innovation/lanes")
    real = next(lane for lane in lanes.json()["lanes"] if lane["id"] == "real_providers")
    assert real["status"] == "ready_local"

    advanced = stage1_client.post("/api/v1/workforce/innovation/advance")
    assert advanced.status_code == 200
    moved = advanced.json()
    assert moved["previous_lane_id"] == "real_providers"
    assert moved["active_lane_id"] == "companion_soul"

    after = stage1_client.get("/api/v1/workforce/innovation")
    assert after.json()["active_lane_id"] == "companion_soul"
