"""Live HTTP contract tests — real TCP against the local contract backend.

Proves mock → http clients, forge smoke, and Innovation · Wire without RunPod.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.rate_limit import reset_rate_limiter
from app.main import create_app
from app.models.llm import ChatMessage
from app.services.llm.client import OpenAICompatibleLLMClient, create_llm_client
from app.services.providers.contract_backend import (
    ContractBackendServer,
    start_contract_backend,
)
from app.services.providers.forge import ProviderContractForge
from app.services.providers.probe import ProviderProbeService
from app.services.tts.client import create_tts_client
from app.services.video.client import create_musetalk_client
from app.services.video.sync import SyncTimeline


def _patch_settings(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> None:
    get_settings.cache_clear()
    monkeypatch.setattr("app.core.config.get_settings", lambda: settings)
    monkeypatch.setattr("app.core.lifecycle.get_settings", lambda: settings)


@pytest.fixture(scope="module")
def contract_backend() -> Iterator[ContractBackendServer]:
    server = start_contract_backend()
    try:
        yield server
    finally:
        server.stop()


def _http_settings(backend: ContractBackendServer, tmp_path: Path) -> Settings:
    return Settings(
        llm_provider="openai_compatible",
        llm_base_url=backend.llm_base_url,
        tts_provider="http",
        tts_base_url=backend.tts_base_url,
        video_provider="http",
        video_base_url=backend.video_base_url,
        llm_api_key="",
        mock_realistic=False,
        provider_gate_enabled=True,
        provider_gate_allow_degraded=True,
        companion_persist_enabled=False,
        api_key_enabled=False,
        rate_limit_enabled=False,
        runpod_wiring_path=str(tmp_path / "runpod_wiring.json"),
        innovation_lanes_path=str(tmp_path / "innovation_lanes.json"),
    )


@pytest.mark.asyncio
async def test_http_clients_against_local_contract(
    contract_backend: ContractBackendServer, tmp_path: Path
) -> None:
    settings = _http_settings(contract_backend, tmp_path)

    llm = create_llm_client(settings)
    tts = create_tts_client(settings)
    video = create_musetalk_client(settings)
    try:
        tokens: list[str] = []
        async for token in llm.stream_tokens(
            [ChatMessage(role="user", content="Say hi.")],
            max_tokens=16,
            temperature=0.0,
        ):
            tokens.append(token)
        assert tokens
        assert "heard" in "".join(tokens).lower()

        audio = await tts.synthesize("Ok.")
        assert audio.pcm_bytes
        assert audio.duration_ms > 0

        timeline = SyncTimeline(fps=settings.video_fps)
        result = await video.generate_frames(
            audio_b64="AQID",
            sample_rate=settings.tts_sample_rate,
            channels=settings.tts_channels,
            duration_ms=200,
            timeline=timeline,
            avatar_id="default",
        )
        assert result.frames
        assert result.frames[0].frame_b64
    finally:
        await llm.aclose()
        await tts.aclose()
        await video.aclose()


@pytest.mark.asyncio
async def test_forge_live_smoke_against_local_contract(
    contract_backend: ContractBackendServer, tmp_path: Path
) -> None:
    settings = _http_settings(contract_backend, tmp_path)
    probe = ProviderProbeService(settings=settings)
    forge = ProviderContractForge(settings, probe=probe)
    try:
        report = await forge.evaluate_all(live_smoke=True)
        assert report.forge_ok is True
        assert report.llm.mode == "openai_compatible"
        assert report.tts.mode == "http"
        assert report.video.mode == "http"
        assert report.llm.smoke_ok is True
        assert report.tts.smoke_ok is True
        assert report.video.smoke_ok is True
        assert report.llm.probe_status in ("ok", "degraded")
    finally:
        await probe.aclose()


@pytest.mark.asyncio
async def test_llm_non_stream_json_fallback(
    contract_backend: ContractBackendServer, tmp_path: Path
) -> None:
    settings = _http_settings(contract_backend, tmp_path)
    client = OpenAICompatibleLLMClient(settings)
    original_stream = client._client.stream

    def force_json_stream(method: str, path: str, **kwargs: object):
        headers = dict(kwargs.pop("headers", {}) or {})
        headers["X-Contract-Mode"] = "json"
        return original_stream(method, path, headers=headers, **kwargs)

    client._client.stream = force_json_stream  # type: ignore[method-assign]
    try:
        tokens: list[str] = []
        async for token in client.stream_tokens(
            [ChatMessage(role="user", content="json mode")],
            max_tokens=8,
            temperature=0.0,
        ):
            tokens.append(token)
        assert tokens
        assert "json mode" in "".join(tokens).lower()
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_tts_json_without_content_type(
    contract_backend: ContractBackendServer, tmp_path: Path
) -> None:
    settings = _http_settings(contract_backend, tmp_path)
    client = create_tts_client(settings)
    original_post = client._client.post

    async def post_no_ctype(path: str, **kwargs: object):
        headers = dict(kwargs.pop("headers", {}) or {})
        headers["X-Contract-Mode"] = "json-no-ctype"
        return await original_post(path, headers=headers, **kwargs)

    client._client.post = post_no_ctype  # type: ignore[method-assign]
    try:
        audio = await client.synthesize("No content type")
        assert audio.pcm_bytes
        assert audio.duration_ms > 0
    finally:
        await client.aclose()


def test_app_forge_and_perform_over_http(
    contract_backend: ContractBackendServer,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    settings = _http_settings(contract_backend, tmp_path)
    _patch_settings(monkeypatch, settings)
    reset_rate_limiter()
    with TestClient(create_app()) as client:
        forge = client.get("/api/v1/providers/forge")
        assert forge.status_code == 200
        assert forge.json()["llm"]["mode"] == "openai_compatible"

        smoke = client.post("/api/v1/providers/forge/smoke")
        assert smoke.status_code == 200
        body = smoke.json()
        assert body["forge_ok"] is True
        assert body["llm"]["smoke_ok"] is True
        assert body["tts"]["smoke_ok"] is True
        assert body["video"]["smoke_ok"] is True

        ready = client.get("/api/v1/health/ready")
        assert ready.status_code == 200

        perform = client.post(
            "/api/v1/chat/perform",
            json={
                "max_tokens": 8,
                "messages": [{"role": "user", "content": "One word."}],
            },
        )
        assert perform.status_code == 200
        assert "data:" in perform.text
        assert '"type": "token"' in perform.text or '"type":"token"' in perform.text
    get_settings.cache_clear()


def test_innovation_wire_localhost_activates_http(
    contract_backend: ContractBackendServer,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
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
    )
    _patch_settings(monkeypatch, settings)
    reset_rate_limiter()
    with TestClient(create_app()) as client:
        wired = client.post(
            "/api/v1/workforce/innovation/wire",
            json={
                "llm_base_url": contract_backend.llm_base_url,
                "tts_base_url": contract_backend.tts_base_url,
                "video_base_url": contract_backend.video_base_url,
                "enabled": True,
            },
        )
        assert wired.status_code == 200
        body = wired.json()
        assert body["wired"] is True
        assert body["pipelines_activated"] is True
        assert body["effective_providers"]["llm"] == "openai_compatible"

        smoke = client.post("/api/v1/providers/forge/smoke")
        assert smoke.status_code == 200
        assert smoke.json()["forge_ok"] is True
        assert client.app.state.llm_pipeline.provider == "openai_compatible"
    get_settings.cache_clear()
