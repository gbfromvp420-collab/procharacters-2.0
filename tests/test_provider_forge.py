"""Tests for Real Provider Forge layer (Phase 12)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.providers.contracts import is_placeholder_endpoint
from app.services.providers.forge import ProviderContractForge
from app.services.providers.probe import ProviderProbeService


@pytest.fixture
def mock_settings() -> Settings:
    return Settings(
        llm_provider="mock",
        tts_provider="mock",
        video_provider="mock",
    )


@pytest.mark.asyncio
async def test_forge_mock_providers_contract_ok(mock_settings: Settings) -> None:
    probe = ProviderProbeService(settings=mock_settings)
    forge = ProviderContractForge(mock_settings, probe=probe)
    try:
        report = await forge.evaluate_all(live_smoke=True)
        assert report.forge_ok is True
        assert report.llm.contract_ok is True
        assert report.tts.contract_ok is True
        assert report.video.contract_ok is True
        assert report.llm.smoke_ok is True
        assert report.llm.spec.endpoint_path == "/chat/completions"
        assert report.tts.spec.endpoint_path == "/synthesize"
        assert report.video.spec.endpoint_path == "/generate"
    finally:
        await probe.aclose()


@pytest.mark.asyncio
async def test_forge_flags_placeholder_http_endpoint(mock_settings: Settings) -> None:
    settings = mock_settings.model_copy(
        update={
            "tts_provider": "http",
            "tts_base_url": "https://your-runpod-tts-endpoint",
        }
    )
    probe = ProviderProbeService(settings=settings)
    forge = ProviderContractForge(settings, probe=probe)
    try:
        entry = await forge.evaluate_provider("tts", live_smoke=False)
        assert entry.contract_ok is False
        assert "placeholder" in entry.message.lower()
    finally:
        await probe.aclose()


def test_placeholder_endpoint_detection() -> None:
    assert is_placeholder_endpoint("https://your-runpod-tts-endpoint") is True
    assert is_placeholder_endpoint("http://localhost:8002") is False


def test_providers_forge_api() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/providers/forge")
        assert response.status_code == 200
        body = response.json()
        assert body["forge_ok"] is True
        assert body["llm"]["contract_ok"] is True
        assert body["tts"]["contract_ok"] is True
        assert body["video"]["contract_ok"] is True
        assert body["llm"]["spec"]["method"] == "POST"


def test_providers_forge_smoke_api_mock() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/api/v1/providers/forge/smoke")
        assert response.status_code == 200
        body = response.json()
        assert body["live_smoke"] is True
        assert body["forge_ok"] is True
        assert body["llm"]["smoke_ok"] is True