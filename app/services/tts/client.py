import asyncio
import base64
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx

from app.core.config import Settings
from app.services.tts.audio import generate_mock_pcm, pcm_duration_ms

logger = logging.getLogger(__name__)

# =============================================================================
# TTS PROVIDER CONTRACT (http)
# =============================================================================
# Endpoint: POST {tts_base_url}/synthesize
#
# Request:
#   Headers: Content-Type: application/json, (optional) Authorization: Bearer <tts_api_key>
#   JSON body (sent by HttpTTSClient):
#     {
#       "text": "<chunk text>",
#       "voice": "<voice name or default>",
#       "format": "pcm_s16le",
#       "sample_rate": <tts_sample_rate e.g. 24000>,
#       "channels": <tts_channels e.g. 1>
#     }
#
# Response:
#   - Preferred: application/json
#       { "audio_b64": "<base64 of pcm_s16le bytes>", "sample_rate"?: int, "channels"?: int }
#   - Fallback: raw response body = exact PCM bytes (s16le, little endian)
#
# Client returns full audio for the text (batch per chunk). Streaming of audio happens
# at the TTSStreamPipeline level (LLM tokens -> chunked synthesize calls).
#
# Real backends (RunPod etc.) must return timely PCM for short text chunks (20-120 chars).
# Duration is computed client-side from PCM length.
# =============================================================================


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
    """Local mock that returns generated PCM tones for the text.

    Improved realism:
    - Variable duration based on text length + small deterministic jitter
    - Voice affects simulated frequency (still synthetic tone)
    - Delay simulates real synthesis compute time (uses tts_mock_chunk_delay_ms)
    - Produces different lengths per chunk to exercise audio/video timing
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def synthesize(
        self,
        text: str,
        *,
        voice: str | None = None,
    ) -> SynthesizedAudio:
        await asyncio.sleep(self._settings.tts_mock_chunk_delay_ms / 1000)

        # Slight variance for realism: longer text -> longer audio, voice hash affects freq
        v = voice or self._settings.tts_voice
        voice_factor = (hash(v) % 7) - 3
        pcm_bytes = generate_mock_pcm(
            text,
            sample_rate=self._settings.tts_sample_rate,
            ms_per_char=42 + voice_factor * 3,
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
    """Calls a RunPod / remote TTS HTTP endpoint for PCM synthesis (batch per text chunk).

    Resilient features:
    - Granular timeouts (short connect, full read for synthesis)
    - Basic retry (1-2 attempts) on transient network/5xx errors with backoff
    - Response validation: requires audio data (b64 or raw); raises on bad payload
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        headers = {"Content-Type": "application/json"}
        if settings.tts_api_key:
            headers["Authorization"] = f"Bearer {settings.tts_api_key}"

        self._client = httpx.AsyncClient(
            base_url=settings.tts_base_url.rstrip("/"),
            headers=headers,
            timeout=httpx.Timeout(
                connect=8.0,
                read=settings.tts_timeout_seconds,
                write=20.0,
                pool=5.0,
            ),
            limits=httpx.Limits(max_keepalive_connections=3, max_connections=8),
        )
        self._max_retries = 2

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

        last_exc: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                response = await self._client.post("/synthesize", json=payload)
                response.raise_for_status()

                content_type = response.headers.get("content-type", "")
                if "application/json" in content_type:
                    data = response.json()
                    if not isinstance(data, dict) or "audio_b64" not in data:
                        raise ValueError("TTS JSON response missing audio_b64")
                    b64 = data["audio_b64"]
                    if not isinstance(b64, str) or not b64:
                        raise ValueError("Invalid audio_b64 in TTS response")
                    pcm_bytes = base64.b64decode(b64)
                    sample_rate = int(data.get("sample_rate", self._settings.tts_sample_rate))
                    channels = int(data.get("channels", self._settings.tts_channels))
                else:
                    pcm_bytes = response.content
                    if not pcm_bytes:
                        raise ValueError("TTS raw response contained zero bytes")
                    sample_rate = self._settings.tts_sample_rate
                    channels = self._settings.tts_channels

                # Basic validation of PCM length
                if len(pcm_bytes) % (2 * channels) != 0:
                    logger.warning("TTS PCM length not aligned to sample size; may be truncated")
                if len(pcm_bytes) == 0:
                    raise ValueError("TTS returned empty PCM")

                return SynthesizedAudio(
                    pcm_bytes=pcm_bytes,
                    sample_rate=sample_rate,
                    channels=channels,
                    duration_ms=pcm_duration_ms(pcm_bytes, sample_rate, channels),
                )
            except (httpx.ConnectError, httpx.TimeoutException, httpx.ReadError, httpx.HTTPStatusError) as exc:
                last_exc = exc
                if attempt < self._max_retries and (
                    isinstance(exc, (httpx.ConnectError, httpx.TimeoutException))
                    or (isinstance(exc, httpx.HTTPStatusError) and 500 <= exc.response.status_code < 600)
                ):
                    backoff = 0.15 * (attempt + 1)
                    logger.warning("TTS synthesize transient error (attempt %s): %s; retrying in %.2fs", attempt + 1, exc, backoff)
                    await asyncio.sleep(backoff)
                    continue
                raise
            except Exception:
                raise
        if last_exc:
            raise last_exc
        raise RuntimeError("TTS synthesize failed without exception")

    async def aclose(self) -> None:
        await self._client.aclose()


def create_tts_client(settings: Settings) -> TTSClient:
    if settings.tts_provider == "http":
        return HttpTTSClient(settings)
    return MockTTSClient(settings)