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
        """Create (once) the avatar tracks bound to this bridge.

        Idempotent for re-negotiation: safe to call on 2nd+ offers; tracks objects are
        reused across PC re-creates (new PC gets them via addTrack).
        """
        from app.services.webrtc.tracks import AvatarAudioTrack, AvatarVideoTrack

        if self._audio_track is None:
            self._audio_track = AvatarAudioTrack(self)
        if self._video_track is None:
            self._video_track = AvatarVideoTrack(self)
        self._tracks_attached = True
        # Reset clocks on (re)attach to avoid drift on resume/reconnect scenarios
        self._reset_track_clocks()
        return self._audio_track, self._video_track

    async def begin_stream(self) -> None:
        """Reset timeline + queues + track pacing for a new /chat/perform (or resume segment).

        Called on every perform even for same WebRTC session (re-negotiation does not
        require re-begin; this is for media segmenting within session).
        """
        self._audio_timeline_ms = 0
        await self._drain_queue(self._audio_queue)
        await self._drain_queue(self._video_queue)
        self._reset_track_clocks()

    async def ingest_event(self, event: PerformStreamEvent) -> None:
        """Ingest pipeline events into WebRTC queues.

        Robust: early return if closed (e.g. during reconnect/close race).
        Used with same bridge across offers/renegotiations.
        """
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

    def _reset_track_clocks(self) -> None:
        """Reset per-track pacing clocks so multi-turn / resumed performs don't drift or burst."""
        if self._audio_track is not None:
            self._audio_track._clock_start = None
            self._audio_track._clock_origin_ms = None
        if self._video_track is not None:
            self._video_track._clock_start = None
            self._video_track._clock_origin_ms = None