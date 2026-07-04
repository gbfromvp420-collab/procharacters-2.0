"""Tests for Empire Launch layer (Phase 11)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import AsyncMock, patch

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
def empire_client(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[TestClient]:
    settings = Settings(
        llm_provider="mock",
        tts_provider="mock",
        video_provider="mock",
        mock_realistic=False,
        companion_persist_enabled=True,
        companion_persist_path=str(tmp_path / "data" / "companion_sessions.json"),
        kgc_policies_path=str(tmp_path / "data" / "kgc_policies.json"),
        api_key_enabled=False,
        rate_limit_enabled=False,
        deployment_phase=15,
        app_version="0.13.0",
    )
    _patch_settings(monkeypatch, settings)
    reset_rate_limiter()
    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings.cache_clear()


def test_liveness_probe(empire_client: TestClient) -> None:
    response = empire_client.get("/api/v1/health/live")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "alive"
    assert body["version"] == "0.13.0"
    assert body["deployment_phase"] == 15


def test_readiness_probe_ok_with_mock_providers(empire_client: TestClient) -> None:
    response = empire_client.get("/api/v1/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["checks"]["companion_persist"]["ok"] is True
    assert body["checks"]["kgc_policies"]["ok"] is True
    assert body["checks"]["providers"]["ok"] is True


def test_readiness_probe_not_ready_when_providers_blocked(
    empire_client: TestClient,
) -> None:
    with patch(
        "app.services.deploy.readiness.check_providers_ready",
        new=AsyncMock(return_value=(False, "llm provider unreachable: timeout")),
    ):
        response = empire_client.get("/api/v1/health/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["checks"]["providers"]["ok"] is False


def test_health_includes_deployment_phase(empire_client: TestClient) -> None:
    response = empire_client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["deployment_phase"] == 15


def test_live_and_ready_exempt_from_api_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    settings = Settings(
        api_key_enabled=True,
        api_key="secret-key",
        companion_persist_enabled=False,
        rate_limit_enabled=False,
        kgc_policies_path=str(tmp_path / "kgc_policies.json"),
    )
    _patch_settings(monkeypatch, settings)
    reset_rate_limiter()

    with TestClient(create_app()) as client:
        assert client.get("/api/v1/health/live").status_code == 200
        assert client.get("/api/v1/health/ready").status_code == 200
        denied = client.post("/api/v1/webrtc/session")
        assert denied.status_code == 401

    get_settings.cache_clear()