import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx

from app.core.config import Settings
from app.services.video.frames import mock_frame_b64
from app.services.video.sync import SyncTimeline

logger = logging.getLogger(__name__)


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
        frames = [
            GeneratedFrame(frame_index=index, pts_ms=pts_ms, frame_b64=frame_b64)
            for index, pts_ms in frame_slots
        ]

        if frames:
            await asyncio.sleep(self._settings.video_mock_frame_delay_ms / 1000)

        return VideoGenerationResult(
            frames=frames,
            width=self._settings.video_width,
            height=self._settings.video_height,
        )


class HttpMuseTalkClient(MuseTalkClient):
    """Calls a RunPod MuseTalk HTTP service for lip-synced frame generation."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        headers = {"Content-Type": "application/json"}
        if settings.video_api_key:
            headers["Authorization"] = f"Bearer {settings.video_api_key}"

        self._client = httpx.AsyncClient(
            base_url=settings.video_base_url.rstrip("/"),
            headers=headers,
            timeout=httpx.Timeout(settings.video_timeout_seconds),
        )

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

        response = await self._client.post("/generate", json=payload)
        response.raise_for_status()
        data = response.json()

        frames = [
            GeneratedFrame(
                frame_index=int(frame["frame_index"]),
                pts_ms=int(frame["pts_ms"]),
                frame_b64=frame["frame_b64"],
            )
            for frame in data.get("frames", [])
        ]

        timeline.commit_segment(duration_ms, len(frames))
        if not frames:
            logger.warning("MuseTalk backend returned zero frames for %sms audio", duration_ms)

        return VideoGenerationResult(
            frames=frames,
            width=int(data.get("width", self._settings.video_width)),
            height=int(data.get("height", self._settings.video_height)),
        )

    async def aclose(self) -> None:
        await self._client.aclose()


def create_musetalk_client(settings: Settings) -> MuseTalkClient:
    if settings.video_provider == "http":
        return HttpMuseTalkClient(settings)
    return MockMuseTalkClient(settings)