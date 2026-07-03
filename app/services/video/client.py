import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx

from app.core.config import Settings
from app.services.video.frames import mock_frame_b64
from app.services.video.sync import SyncTimeline

logger = logging.getLogger(__name__)

# =============================================================================
# VIDEO / MUSE TALK PROVIDER CONTRACT (http)
# =============================================================================
# Endpoint: POST {video_base_url}/generate
#
# Request:
#   Headers: Content-Type: application/json, (optional) Authorization: Bearer <video_api_key>
#   JSON body:
#     {
#       "audio_b64": "<base64 pcm_s16le>",
#       "sample_rate": int,
#       "channels": int,
#       "duration_ms": int,
#       "avatar_id": str,
#       "fps": int (from settings),
#       "start_pts_ms": int (timeline cursor before this segment),
#       "start_frame_index": int (timeline frame count before)
#     }
#
# Response (JSON):
#   {
#     "frames": [
#       {"frame_index": int, "pts_ms": int, "frame_b64": "<base64 jpeg>"},
#       ...
#     ],
#     "width"?: int,
#     "height"?: int
#   }
#
# Important:
# - One call per audio chunk from TTS (batch generation of N frames for that segment).
# - Client then advances the passed SyncTimeline via commit_segment.
# - Returned frames should be monotonic and roughly fps-matched to duration.
# - Real RunPod MuseTalk endpoints must accept b64 audio + timeline hints and reply quickly.
# - Mocks and HTTP both return GeneratedFrame list; downstream emits VideoFrameEvent per frame.
# =============================================================================


@dataclass(frozen=True)
class GeneratedFrame:
    frame_index: int
    pts_ms: int
    frame_b64: str


@dataclass(frozen=True)
class VideoGenerationResult:
    frames: list[GeneratedFrame]
    width: int
    height: int


class MuseTalkClient(ABC):
    @abstractmethod
    async def generate_frames(
        self,
        *,
        audio_b64: str,
        sample_rate: int,
        channels: int,
        duration_ms: int,
        timeline: SyncTimeline,
        avatar_id: str,
    ) -> VideoGenerationResult:
        raise NotImplementedError

    async def aclose(self) -> None:
        return None


class MockMuseTalkClient(MuseTalkClient):
    """Local mock for MuseTalk-style lip sync frame generation.

    Realism improvements:
    - Per-frame simulated work using small async sleeps spread across frames
    - Variable frame delay (base + content-derived jitter) instead of single fixed sleep
    - Uses timeline.allocate_frames which produces fps-correct pts
    - Still returns identical placeholder JPEG for decoder compatibility in browser client
    - Respects duration_ms / fps for count
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def generate_frames(
        self,
        *,
        audio_b64: str,
        sample_rate: int,
        channels: int,
        duration_ms: int,
        timeline: SyncTimeline,
        avatar_id: str,
    ) -> VideoGenerationResult:
        del audio_b64, sample_rate, channels, avatar_id

        frame_slots = timeline.allocate_frames(duration_ms)
        frame_b64 = mock_frame_b64()
        base_delay = self._settings.video_mock_frame_delay_ms / 1000.0

        frames: list[GeneratedFrame] = []
        for idx, (index, pts_ms) in enumerate(frame_slots):
            frames.append(
                GeneratedFrame(frame_index=index, pts_ms=pts_ms, frame_b64=frame_b64)
            )
            # Spread "compute" cost realistically across frames (small per-frame yield)
            if idx % 3 == 0 or len(frame_slots) <= 2:
                jitter = ((hash(str(pts_ms)) % 5) - 2) * 0.003
                await asyncio.sleep(max(0.001, base_delay + jitter))

        return VideoGenerationResult(
            frames=frames,
            width=self._settings.video_width,
            height=self._settings.video_height,
        )


class HttpMuseTalkClient(MuseTalkClient):
    """Calls a RunPod MuseTalk HTTP service for lip-synced frame generation.

    Resilient features:
    - Granular timeouts tuned for potentially heavy video gen
    - Retry on transient 5xx / network errors (video gen can be flaky)
    - Strict validation of returned frames array and required fields
    - Warns and skips malformed frames instead of total failure where safe
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        headers = {"Content-Type": "application/json"}
        if settings.video_api_key:
            headers["Authorization"] = f"Bearer {settings.video_api_key}"

        self._client = httpx.AsyncClient(
            base_url=settings.video_base_url.rstrip("/"),
            headers=headers,
            timeout=httpx.Timeout(
                connect=10.0,
                read=settings.video_timeout_seconds,
                write=30.0,
                pool=5.0,
            ),
            limits=httpx.Limits(max_keepalive_connections=2, max_connections=6),
        )
        self._max_retries = 1  # video jobs are expensive; limited retries

    async def generate_frames(
        self,
        *,
        audio_b64: str,
        sample_rate: int,
        channels: int,
        duration_ms: int,
        timeline: SyncTimeline,
        avatar_id: str,
    ) -> VideoGenerationResult:
        payload = {
            "audio_b64": audio_b64,
            "sample_rate": sample_rate,
            "channels": channels,
            "duration_ms": duration_ms,
            "avatar_id": avatar_id,
            "fps": self._settings.video_fps,
            "start_pts_ms": timeline.audio_cursor_ms,
            "start_frame_index": timeline.frame_index,
        }

        last_exc: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                response = await self._client.post("/generate", json=payload)
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, dict):
                    raise ValueError("MuseTalk response is not a JSON object")

                raw_frames = data.get("frames", [])
                if not isinstance(raw_frames, list):
                    raw_frames = []

                frames: list[GeneratedFrame] = []
                for frame in raw_frames:
                    if not isinstance(frame, dict):
                        continue
                    try:
                        fi = int(frame["frame_index"])
                        pts = int(frame["pts_ms"])
                        fb64 = frame["frame_b64"]
                        if not isinstance(fb64, str) or len(fb64) < 10:
                            logger.warning("Skipping invalid frame_b64 in video response")
                            continue
                        frames.append(
                            GeneratedFrame(frame_index=fi, pts_ms=pts, frame_b64=fb64)
                        )
                    except (KeyError, ValueError, TypeError) as parse_err:
                        logger.warning("Skipping malformed video frame: %s", parse_err)
                        continue

                num = len(frames)
                timeline.commit_segment(duration_ms, num)
                if num == 0:
                    logger.warning("MuseTalk backend returned zero valid frames for %sms audio", duration_ms)

                return VideoGenerationResult(
                    frames=frames,
                    width=int(data.get("width", self._settings.video_width)),
                    height=int(data.get("height", self._settings.video_height)),
                )
            except (httpx.ConnectError, httpx.TimeoutException, httpx.ReadError, httpx.HTTPStatusError) as exc:
                last_exc = exc
                if attempt < self._max_retries and (
                    isinstance(exc, (httpx.ConnectError, httpx.TimeoutException))
                    or (isinstance(exc, httpx.HTTPStatusError) and 500 <= exc.response.status_code < 600)
                ):
                    backoff = 0.3 * (attempt + 1)
                    logger.warning("Video /generate transient error (attempt %s): %s; retrying", attempt + 1, exc)
                    await asyncio.sleep(backoff)
                    continue
                raise
            except Exception:
                raise
        if last_exc:
            raise last_exc
        raise RuntimeError("Video generate_frames failed")

    async def aclose(self) -> None:
        await self._client.aclose()


def create_musetalk_client(settings: Settings) -> MuseTalkClient:
    if settings.video_provider == "http":
        return HttpMuseTalkClient(settings)
    return MockMuseTalkClient(settings)