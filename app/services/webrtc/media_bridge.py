import asyncio
import base64
import logging
from typing import TYPE_CHECKING

from app.core.config import Settings
from app.models.llm import StreamDoneEvent, StreamErrorEvent
from app.models.tts import AudioChunkEvent, TTSDoneEvent, TTSErrorEvent
from app.models.video import VideoFrameEvent, VideoSyncDoneEvent, VideoSyncErrorEvent
from app.services.video.pipeline import PerformStreamEvent
from app.services.webrtc.frame_utils import pcm_b64_to_audio_packets
from app.services.webrtc.packets import AudioPacket, VideoPacket
if TYPE_CHECKING:
    from app.services.webrtc.tracks import AvatarAudioTrack, AvatarVideoTrack

logger = logging.getLogger(__name__)

_QUEUE_SENTINEL = object()


class AvatarMediaBridge:
    """Async media queues bridging /chat/perform output to WebRTC tracks."""

    def __init__(
        self,
        session_id: str,
        *,
        settings: Settings,
    ) -> None:
        self.session_id = session_id
        self._settings = settings
        self._audio_queue: asyncio.Queue[AudioPacket | object] = asyncio.Queue()
        self._video_queue: asyncio.Queue[VideoPacket | object] = asyncio.Queue()
        self._closed = asyncio.Event()
        self._tracks_attached = False
        self._audio_timeline_ms = 0
        self._audio_track: "AvatarAudioTrack | None" = None
        self._video_track: "AvatarVideoTrack | None" = None

    @property
    def is_closed(self) -> bool:
        return self._closed.is_set()

    @property
    def tracks_attached(self) -> bool:
        return self._tracks_attached

    def attach_tracks(self) -> tuple["AvatarAudioTrack", "AvatarVideoTrack"]:
        from app.services.webrtc.tracks import AvatarAudioTrack, AvatarVideoTrack

        if self._audio_track is None:
            self._audio_track = AvatarAudioTrack(self)
        if self._video_track is None:
            self._video_track = AvatarVideoTrack(self)
        self._tracks_attached = True
        return self._audio_track, self._video_track

    async def begin_stream(self) -> None:
        """Reset timeline state for a new /chat/perform invocation."""
        self._audio_timeline_ms = 0
        await self._drain_queue(self._audio_queue)
        await self._drain_queue(self._video_queue)

    async def ingest_event(self, event: PerformStreamEvent) -> None:
        if self.is_closed:
            return

        if isinstance(event, AudioChunkEvent):
            await self.push_audio_chunk(event)
        elif isinstance(event, VideoFrameEvent):
            await self.push_video_frame(event)
        elif isinstance(event, (StreamErrorEvent, TTSErrorEvent, VideoSyncErrorEvent)):
            await self.close(reason=f"pipeline_error:{event.type}")
        elif isinstance(event, (StreamDoneEvent, VideoSyncDoneEvent, TTSDoneEvent)):
            await self.signal_segment_end()

    async def push_audio_chunk(self, chunk: AudioChunkEvent) -> None:
        if self.is_closed:
            return

        packets = pcm_b64_to_audio_packets(
            chunk.audio_b64,
            sample_rate=chunk.sample_rate,
            channels=chunk.channels,
            start_pts_ms=self._audio_timeline_ms,
        )
        for packet in packets:
            await self._audio_queue.put(packet)

        self._audio_timeline_ms += chunk.duration_ms

    async def push_video_frame(self, frame: VideoFrameEvent) -> None:
        if self.is_closed:
            return

        packet = VideoPacket(
            jpeg_bytes=base64.b64decode(frame.frame_b64),
            width=frame.width,
            height=frame.height,
            frame_index=frame.frame_index,
            pts_ms=frame.pts_ms,
        )
        await self._video_queue.put(packet)

    async def get_audio_packet(self) -> AudioPacket | None:
        item = await self._audio_queue.get()
        if item is _QUEUE_SENTINEL or self.is_closed:
            return None
        return item  # type: ignore[return-value]

    async def get_video_packet(self) -> VideoPacket | None:
        item = await self._video_queue.get()
        if item is _QUEUE_SENTINEL or self.is_closed:
            return None
        return item  # type: ignore[return-value]

    async def signal_segment_end(self) -> None:
        """Marks the end of one perform segment without tearing down the peer."""
        logger.debug("Perform segment ended for session %s", self.session_id)

    async def close(self, *, reason: str = "explicit") -> None:
        if self.is_closed:
            return

        self._closed.set()
        logger.info("Closing media bridge for session %s (%s)", self.session_id, reason)

        await self._audio_queue.put(_QUEUE_SENTINEL)
        await self._video_queue.put(_QUEUE_SENTINEL)

        if self._audio_track is not None:
            await self._audio_track.aclose()
        if self._video_track is not None:
            await self._video_track.aclose()

    async def _drain_queue(self, queue: asyncio.Queue[object]) -> None:
        while not queue.empty():
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                break