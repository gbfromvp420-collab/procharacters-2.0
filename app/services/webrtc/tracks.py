import asyncio
import logging
import time
from typing import TYPE_CHECKING, Literal

from aiortc import MediaStreamError
from aiortc.mediastreams import AudioStreamTrack, VideoStreamTrack
from av import AudioFrame, VideoFrame

from app.services.webrtc.frame_utils import (
    audio_packet_to_frame,
    jpeg_bytes_to_video_frame,
    pts_ms_to_video_pts,
    video_time_base,
)

if TYPE_CHECKING:
    from app.services.webrtc.media_bridge import AvatarMediaBridge

logger = logging.getLogger(__name__)


class AvatarVideoTrack(VideoStreamTrack):
    kind: Literal["video"] = "video"

    def __init__(self, bridge: "AvatarMediaBridge") -> None:
        super().__init__()
        self._bridge = bridge
        self._clock_origin_ms: int | None = None
        self._clock_start: float | None = None
    async def recv(self) -> VideoFrame:
        if self.readyState != "live" or self._bridge.is_closed:
            raise MediaStreamError

        packet = await self._bridge.get_video_packet()
        if packet is None:
            await self.aclose()
            raise MediaStreamError

        await self._pace(packet.pts_ms)

        frame = jpeg_bytes_to_video_frame(
            packet.jpeg_bytes,
            pts_ms=packet.pts_ms,
            target_width=packet.width,
            target_height=packet.height,
        )

        # Enforce interval-based PTS at the configured FPS to prevent drift.
        frame.pts = pts_ms_to_video_pts(packet.pts_ms)
        frame.time_base = video_time_base()
        return frame

    async def _pace(self, pts_ms: int) -> None:
        if self._clock_start is None:
            self._clock_start = time.time()
            self._clock_origin_ms = pts_ms
            return

        origin = self._clock_origin_ms or 0
        target = self._clock_start + (pts_ms - origin) / 1000.0
        wait = target - time.time()
        if wait > 0:
            await asyncio.sleep(wait)

    async def aclose(self) -> None:
        if self.readyState != "live":
            return
        self.stop()
        logger.debug("AvatarVideoTrack closed for session %s", self._bridge.session_id)


class AvatarAudioTrack(AudioStreamTrack):
    kind: Literal["audio"] = "audio"

    def __init__(self, bridge: "AvatarMediaBridge") -> None:
        super().__init__()
        self._bridge = bridge
        self._clock_origin_ms: int | None = None
        self._clock_start: float | None = None

    async def recv(self) -> AudioFrame:
        if self.readyState != "live" or self._bridge.is_closed:
            raise MediaStreamError

        packet = await self._bridge.get_audio_packet()
        if packet is None:
            await self.aclose()
            raise MediaStreamError

        await self._pace(packet.pts_ms)
        return audio_packet_to_frame(packet)

    async def _pace(self, pts_ms: int) -> None:
        if self._clock_start is None:
            self._clock_start = time.time()
            self._clock_origin_ms = pts_ms
            return

        origin = self._clock_origin_ms or 0
        target = self._clock_start + (pts_ms - origin) / 1000.0
        wait = target - time.time()
        if wait > 0:
            await asyncio.sleep(wait)

    async def aclose(self) -> None:
        if self.readyState != "live":
            return
        self.stop()
        logger.debug("AvatarAudioTrack closed for session %s", self._bridge.session_id)