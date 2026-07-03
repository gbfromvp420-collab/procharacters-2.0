import asyncio
import base64
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx

from app.core.config import Settings
from app.services.tts.audio import generate_mock_pcm, pcm_duration_ms

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SynthesizedAudio:
    pcm_bytes: bytes
    sample_rate: int
    channels: int
    duration_ms: int


class TTSClient(ABC):
    @abstractmethod
    async def synthesize(
        self,
        text: str,
        *,
        voice: str | None = None,
    ) -> SynthesizedAudio:
        raise NotImplementedError

    async def aclose(self) -> None:
        return None


class MockTTSClient(TTSClient):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def synthesize(
        self,
        text: str,
        *,
        voice: str | None = None,
    ) -> SynthesizedAudio:
        del voice
        await asyncio.sleep(self._settings.tts_mock_chunk_delay_ms / 1000)

        pcm_bytes = generate_mock_pcm(
            text,
            sample_rate=self._settings.tts_sample_rate,
        )
        return SynthesizedAudio(
            pcm_bytes=pcm_bytes,
            sample_rate=self._settings.tts_sample_rate,
            channels=self._settings.tts_channels,
            duration_ms=pcm_duration_ms(
                pcm_bytes,
                self._settings.tts_sample_rate,
                self._settings.tts_channels,
            ),
        )


class HttpTTSClient(TTSClient):
    """Streams synthesis requests to a RunPod / remote TTS HTTP endpoint."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        headers = {"Content-Type": "application/json"}
        if settings.tts_api_key:
            headers["Authorization"] = f"Bearer {settings.tts_api_key}"

        self._client = httpx.AsyncClient(
            base_url=settings.tts_base_url.rstrip("/"),
            headers=headers,
            timeout=httpx.Timeout(settings.tts_timeout_seconds),
        )

    async def synthesize(
        self,
        text: str,
        *,
        voice: str | None = None,
    ) -> SynthesizedAudio:
        payload = {
            "text": text,
            "voice": voice or self._settings.tts_voice,
            "format": "pcm_s16le",
            "sample_rate": self._settings.tts_sample_rate,
            "channels": self._settings.tts_channels,
        }

        response = await self._client.post("/synthesize", json=payload)
        response.raise_for_status()

        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            data = response.json()
            pcm_bytes = base64.b64decode(data["audio_b64"])
            sample_rate = int(data.get("sample_rate", self._settings.tts_sample_rate))
            channels = int(data.get("channels", self._settings.tts_channels))
        else:
            pcm_bytes = response.content
            sample_rate = self._settings.tts_sample_rate
            channels = self._settings.tts_channels

        return SynthesizedAudio(
            pcm_bytes=pcm_bytes,
            sample_rate=sample_rate,
            channels=channels,
            duration_ms=pcm_duration_ms(pcm_bytes, sample_rate, channels),
        )

    async def aclose(self) -> None:
        await self._client.aclose()


def create_tts_client(settings: Settings) -> TTSClient:
    if settings.tts_provider == "http":
        return HttpTTSClient(settings)
    return MockTTSClient(settings)