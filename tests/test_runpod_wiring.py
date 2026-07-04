"""Tests for RunPod wiring — paste URLs once, app goes real."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.rate_limit import reset_rate_limiter
from app.core.runpod_wiring import (
    apply_runpod_wiring,
    build_wiring_report,
    update_wiring_urls,
    wiring_readiness,
)
from app.main import create_app

_LLM = "https://abc123-8000.proxy.runpod.net/v1"
_TTS = "https://abc123-8002.proxy.runpod.net"
_VIDEO = "https://abc123-8003.proxy.runpod.net"


def _patch_settings(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> None:
    get_settings.cache_clear()
    monkeypatch.setattr("app.core.config.get_settings", lambda: settings)
    monkeypatch.setattr("app.core.lifecycle.get_settings", lambda: settings)


@pytest.fixture
def wiring_client(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[TestClient]:
    wiring_path = tmp_path / "runpod_wiring.json"
    settings = Settings(
        llm_provider="mock",
        tts_provider="mock",
        video_provider="mock",
        mock_realistic=False,
        companion_persist_enabled=False,
        api_key_enabled=False,
        rate_limit_enabled=False,
        runpod_wiring_path=str(wiring_path),
        deployment_phase=20,
        app_version="1.0.0",
    )
    _patch_settings(monkeypatch, settings)
    reset_rate_limiter()
    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings.cache_clear()


def test_wiring_readiness_requires_all_urls() -> None:
    wiring = {
        "enabled": False,
        "llm": {"provider": "openai_compatible", "base_url": _LLM},
        "tts": {"provider": "http", "base_url": ""},
        "video": {"provider": "http", "base_url": _VIDEO},
    }
    readiness = wiring_readiness(wiring)
    assert readiness["llm_ready"] is True
    assert readiness["tts_ready"] is False
    assert readiness["all_ready"] is False
    assert readiness["wired"] is False


def test_apply_runpod_wiring_when_enabled(tmp_path: Path) -> None:
    wiring_path = tmp_path / "runpod_wiring.json"
    wiring_path.write_text(
        json.dumps(
            {
                "enabled": True,
                "llm": {"provider": "openai_compatible", "base_url": _LLM, "api_key": "k1"},
                "tts": {"provider": "http", "base_url": _TTS, "api_key": "k2"},
                "video": {"provider": "http", "base_url": _VIDEO, "api_key": "k3"},
            }
        ),
        encoding="utf-8",
    )
    base = Settings(llm_provider="mock", tts_provider="mock", video_provider="mock")
    effective = apply_runpod_wiring(base.model_copy(update={"runpod_wiring_path": str(wiring_path)}))
    assert effective.llm_provider == "openai_compatible"
    assert effective.llm_base_url == _LLM
    assert effective.tts_base_url == _TTS
    assert effective.video_base_url == _VIDEO


def test_apply_runpod_wiring_skips_when_disabled(tmp_path: Path) -> None:
    wiring_path = tmp_path / "runpod_wiring.json"
    wiring_path.write_text(
        json.dumps(
            {
                "enabled": False,
                "llm": {"provider": "openai_compatible", "base_url": _LLM},
                "tts": {"provider": "http", "base_url": _TTS},
                "video": {"provider": "http", "base_url": _VIDEO},
            }
        ),
        encoding="utf-8",
    )
    base = Settings(llm_provider="mock", runpod_wiring_path=str(wiring_path))
    effective = apply_runpod_wiring(base)
    assert effective.llm_provider == "mock"


def test_update_wiring_urls_auto_enables(tmp_path: Path) -> None:
    path = str(tmp_path / "runpod_wiring.json")
    wiring = update_wiring_urls(
        path=path,
        llm_base_url=_LLM,
        tts_base_url=_TTS,
        video_base_url=_VIDEO,
        api_key="shared-key",
    )
    assert wiring["enabled"] is True
    assert wiring["llm"]["base_url"] == _LLM
    assert wiring["tts"]["api_key"] == "shared-key"


def test_innovation_wiring_get_empty(wiring_client: TestClient) -> None:
    response = wiring_client.get("/api/v1/workforce/innovation/wiring")
    assert response.status_code == 200
    body = response.json()
    assert body["readiness"]["wired"] is False
    assert body["readiness"]["all_ready"] is False
    assert "Paste" in body["message"]


def test_innovation_wire_post(wiring_client: TestClient) -> None:
    response = wiring_client.post(
        "/api/v1/workforce/innovation/wire",
        json={
            "llm_base_url": _LLM,
            "tts_base_url": _TTS,
            "video_base_url": _VIDEO,
            "enabled": True,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["wired"] is True
    assert body["readiness"]["all_ready"] is True
    assert body["env_snippet"] is not None
    assert "LLM_BASE_URL" in body["env_snippet"]


def test_build_wiring_report_env_snippet(tmp_path: Path) -> None:
    wiring_path = tmp_path / "runpod_wiring.json"
    wiring_path.write_text(
        json.dumps(
            {
                "enabled": True,
                "llm": {"provider": "openai_compatible", "base_url": _LLM},
                "tts": {"provider": "http", "base_url": _TTS},
                "video": {"provider": "http", "base_url": _VIDEO},
            }
        ),
        encoding="utf-8",
    )
    settings = Settings(runpod_wiring_path=str(wiring_path))
    report = build_wiring_report(settings)
    assert report["readiness"]["wired"] is True
    assert report["env_snippet"] is not None
    assert _LLM in report["env_snippet"]