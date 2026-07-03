"""Tests for provider probes and companion catalog."""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.companion.catalog import (
    get_avatar_catalog,
    get_prompt_presets,
    get_relationship_modes,
    get_voice_catalog,
)
from app.services.providers.probe import ProviderProbeService


@pytest.fixture
def mock_settings() -> Settings:
    return Settings(
        llm_provider="mock",
        tts_provider="mock",
        video_provider="mock",
        companion_avatars=["default", "professional", "casual"],
        companion_voices=["default", "warm", "bright"],
    )


@pytest.mark.asyncio
async def test_mock_providers_always_ok(mock_settings: Settings) -> None:
    probe = ProviderProbeService(settings=mock_settings)
    try:
        llm = await probe.probe_llm()
        tts = await probe.probe_tts()
        video = await probe.probe_video()
        all_status = await probe.probe_all()

        for status in (llm, tts, video):
            assert status.status == "ok"
            assert status.latency_ms == 0
            assert status.message == "mock"

        assert set(all_status) == {"llm", "tts", "video"}
        assert all_status["llm"].mode == "mock"
    finally:
        await probe.aclose()


@pytest.mark.asyncio
async def test_http_provider_unreachable(mock_settings: Settings) -> None:
    settings = mock_settings.model_copy(
        update={
            "tts_provider": "http",
            "tts_base_url": "http://unreachable.test:9999",
        }
    )
    probe = ProviderProbeService(settings=settings)

    async def unreachable_request(*args: object, **kwargs: object) -> MagicMock:
        raise httpx.ConnectError("connection refused")

    probe._client.request = AsyncMock(side_effect=unreachable_request)  # type: ignore[method-assign]

    try:
        status = await probe.probe_tts()
        assert status.status == "unreachable"
        assert status.mode == "http"
        assert status.provider == "tts"
        assert status.latency_ms >= 0
        assert "connection refused" in status.message or status.message == "connection refused"
    finally:
        await probe.aclose()


def test_catalog_returns_expected_avatars(mock_settings: Settings) -> None:
    avatars = get_avatar_catalog(mock_settings)
    voices = get_voice_catalog(mock_settings)
    presets = get_prompt_presets()

    avatar_ids = [item.id for item in avatars]
    assert avatar_ids == ["default", "professional", "casual"]

    default = avatars[0]
    assert default.label == "Default"
    assert default.emoji == "🙂"
    assert default.accent_color.startswith("#")

    professional = next(a for a in avatars if a.id == "professional")
    assert professional.label == "Professional"
    assert professional.emoji == "💼"

    voice_ids = [item.id for item in voices]
    assert voice_ids == ["default", "warm", "bright"]

    preset_ids = [item.id for item in presets]
    assert preset_ids == ["friendly", "professional_coach", "storyteller"]
    assert all(item.prompt for item in presets)

    modes = get_relationship_modes(mock_settings)
    mode_ids = [item.id for item in modes]
    assert mode_ids == ["friendly", "flirtatious", "romantic", "deep"]
    assert modes[3].label == "Deep"


@pytest.fixture
def api_client() -> TestClient:
    with TestClient(create_app()) as client:
        yield client


def test_providers_status_api_mock(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/providers/status")
    assert response.status_code == 200
    body = response.json()
    for name in ("llm", "tts", "video"):
        assert body[name]["status"] == "ok"
        assert body[name]["message"] == "mock"


def test_companion_catalog_api(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/companion/catalog")
    assert response.status_code == 200
    body = response.json()

    avatar_ids = [item["id"] for item in body["avatars"]]
    assert avatar_ids == ["default", "professional", "casual"]
    assert body["avatars"][0]["label"] == "Default"
    assert "description" in body["avatars"][0]
    assert "accent_color" in body["avatars"][0]
    assert "emoji" in body["avatars"][0]

    voice_ids = [item["id"] for item in body["voices"]]
    assert voice_ids == ["default", "warm", "bright"]

    assert len(body["prompt_presets"]) == 3
    assert body["prompt_presets"][0]["id"] == "friendly"

    mode_ids = [item["id"] for item in body["relationship_modes"]]
    assert mode_ids == ["friendly", "flirtatious", "romantic", "deep"]
    assert all(item["system_prompt_overlay"] for item in body["relationship_modes"])


def test_health_includes_providers_summary(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert "providers_summary" in body
    assert body["providers_summary"]["llm"]["status"] == "ok"
    assert body["providers_summary"]["tts"]["status"] == "ok"
    assert body["providers_summary"]["video"]["status"] == "ok"