"""Tests for provider readiness gate on chat perform/speak."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.models.llm import ChatMessage, ChatRequest
from app.models.providers import ProviderStatus
from app.services.providers.gate import check_providers_ready
from app.services.providers.probe import ProviderProbeService


def _chat_payload() -> dict:
    return {
        "messages": [{"role": "user", "content": "Hello"}],
    }


@pytest.fixture
def mock_settings() -> Settings:
    return Settings(
        llm_provider="mock",
        tts_provider="mock",
        video_provider="mock",
        provider_gate_enabled=True,
        provider_gate_allow_degraded=True,
    )


def _mock_app(settings: Settings, probe: ProviderProbeService) -> SimpleNamespace:
    return SimpleNamespace(
        state=SimpleNamespace(
            settings=settings,
            provider_probe=probe,
        )
    )


@pytest.mark.asyncio
async def test_mock_mode_always_passes(mock_settings: Settings) -> None:
    probe = ProviderProbeService(settings=mock_settings)
    app = _mock_app(mock_settings, probe)
    try:
        for required in (["llm"], ["llm", "tts"], ["llm", "tts", "video"]):
            ok, message = await check_providers_ready(app, required)
            assert ok is True
            assert message == ""
    finally:
        await probe.aclose()


@pytest.mark.asyncio
async def test_http_unreachable_blocks_when_gate_on(mock_settings: Settings) -> None:
    settings = mock_settings.model_copy(
        update={
            "tts_provider": "http",
            "tts_base_url": "http://unreachable.test:9999",
        }
    )
    probe = ProviderProbeService(settings=settings)
    unreachable = ProviderStatus(
        provider="tts",
        mode="http",
        status="unreachable",
        latency_ms=12,
        endpoint=settings.tts_base_url,
        message="connection refused",
    )
    probe.probe_tts = AsyncMock(return_value=unreachable)  # type: ignore[method-assign]
    probe.probe_llm = AsyncMock(
        return_value=ProviderStatus(
            provider="llm",
            mode="mock",
            status="ok",
            latency_ms=0,
            endpoint=settings.llm_base_url,
            message="mock",
        )
    )
    probe.probe_video = AsyncMock(
        return_value=ProviderStatus(
            provider="video",
            mode="mock",
            status="ok",
            latency_ms=0,
            endpoint=settings.video_base_url,
            message="mock",
        )
    )

    app = _mock_app(settings, probe)
    try:
        ok, message = await check_providers_ready(app, ["llm", "tts"])
        assert ok is False
        assert "tts provider unreachable" in message
        assert "connection refused" in message
    finally:
        await probe.aclose()


@pytest.mark.asyncio
async def test_gate_disabled_skips_unreachable(mock_settings: Settings) -> None:
    settings = mock_settings.model_copy(
        update={
            "tts_provider": "http",
            "provider_gate_enabled": False,
        }
    )
    probe = ProviderProbeService(settings=settings)
    probe.probe_tts = AsyncMock(
        return_value=ProviderStatus(
            provider="tts",
            mode="http",
            status="unreachable",
            latency_ms=5,
            endpoint=settings.tts_base_url,
            message="connection refused",
        )
    )
    app = _mock_app(settings, probe)
    try:
        ok, message = await check_providers_ready(app, ["tts"])
        assert ok is True
        assert message == ""
    finally:
        await probe.aclose()


def test_speak_endpoint_blocks_unreachable_tts() -> None:
    with TestClient(create_app()) as client:
        app = client.app
        probe: ProviderProbeService = app.state.provider_probe
        gated_settings = app.state.settings.model_copy(
            update={
                "tts_provider": "http",
                "tts_base_url": "http://unreachable.test:9999",
            }
        )
        app.state.settings = gated_settings
        probe.probe_tts = AsyncMock(
            return_value=ProviderStatus(
                provider="tts",
                mode="http",
                status="unreachable",
                latency_ms=8,
                endpoint=gated_settings.tts_base_url,
                message="connection refused",
            )
        )
        probe.probe_llm = AsyncMock(
            return_value=ProviderStatus(
                provider="llm",
                mode="mock",
                status="ok",
                latency_ms=0,
                endpoint=gated_settings.llm_base_url,
                message="mock",
            )
        )

        response = client.post("/api/v1/chat/speak", json=_chat_payload())
        assert response.status_code == 503
        assert "tts provider unreachable" in response.json()["detail"]


def test_perform_mock_providers_pass_gate() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/api/v1/chat/perform", json=_chat_payload())
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert "data:" in response.text