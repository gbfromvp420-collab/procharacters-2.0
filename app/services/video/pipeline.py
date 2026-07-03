import logging
from collections.abc import AsyncIterator

import httpx

from app.core.config import Settings
from app.models.llm import StreamDoneEvent, StreamErrorEvent, StreamTokenEvent
from app.models.tts import AudioChunkEvent, TTSDoneEvent, TTSErrorEvent
from app.models.video import VideoFrameEvent, VideoSyncDoneEvent, VideoSyncErrorEvent
from app.services.llm.pipeline import StreamEvent
from app.services.tts.pipeline import SpeakStreamEvent, TTSStreamEvent
from app.services.video.client import MuseTalkClient, create_musetalk_client
from app.services.video.sync import SyncTimeline

logger = logging.getLogger(__name__)

VideoStreamEvent = VideoFrameEvent | VideoSyncDoneEvent | VideoSyncErrorEvent
PerformStreamEvent = SpeakStreamEvent | VideoStreamEvent


class VideoSyncPipeline:
    """Synchronizes MuseTalk video frames to streamed TTS audio chunks."""

    def __init__(self, settings: Settings | None = None) -> None:
        from app.core.config import get_settings

        self._settings = settings or get_settings()
        self._client: MuseTalkClient = create_musetalk_client(self._settings)

    @property
    def provider(self) -> str:
        return self._settings.video_provider

    @property
    def avatar_id(self) -> str:
        return self._settings.video_avatar_id

    @property
    def fps(self) -> int:
        return self._settings.video_fps

    async def stream_from_audio_chunk(
        self,
        audio_chunk: AudioChunkEvent,
        *,
        timeline: SyncTimeline,
        avatar_id: str | None = None,
    ) -> AsyncIterator[VideoStreamEvent]:
        resolved_avatar = avatar_id or self._settings.video_avatar_id

        try:
            result = await self._client.generate_frames(
                audio_b64=audio_chunk.audio_b64,
                sample_rate=audio_chunk.sample_rate,
                channels=audio_chunk.channels,
                duration_ms=audio_chunk.duration_ms,
                timeline=timeline,
                avatar_id=resolved_avatar,
            )
        except httpx.HTTPStatusError as exc:
            logger.exception("MuseTalk backend returned an error")
            yield VideoSyncErrorEvent(
                message=f"MuseTalk backend error: {exc.response.status_code}",
            )
            return
        except Exception as exc:
            logger.exception("MuseTalk frame generation failed")
            yield VideoSyncErrorEvent(message=str(exc))
            return

        for frame in result.frames:
            yield VideoFrameEvent(
                frame_index=frame.frame_index,
                audio_chunk_index=audio_chunk.chunk_index,
                pts_ms=frame.pts_ms,
                frame_b64=frame.frame_b64,
                width=result.width,
                height=result.height,
                session_id=audio_chunk.session_id,
            )

    async def stream_from_speak_events(
        self,
        events: AsyncIterator[SpeakStreamEvent],
        *,
        session_id: str | None = None,
        avatar_id: str | None = None,
    ) -> AsyncIterator[PerformStreamEvent]:
        timeline = SyncTimeline(fps=self._settings.video_fps)
        total_duration_ms = 0

        async for event in events:
            if isinstance(event, (StreamTokenEvent, StreamErrorEvent)):
                yield event
                if isinstance(event, StreamErrorEvent):
                    return
                continue

            if isinstance(event, AudioChunkEvent):
                yield event
                total_duration_ms += event.duration_ms

                async for video_event in self.stream_from_audio_chunk(
                    event,
                    timeline=timeline,
                    avatar_id=avatar_id,
                ):
                    if isinstance(video_event, VideoSyncErrorEvent):
                        yield video_event
                        return
                    yield video_event
                continue

            if isinstance(event, TTSErrorEvent):
                yield event
                return

            if isinstance(event, TTSDoneEvent):
                yield event
                continue

            if isinstance(event, StreamDoneEvent):
                yield VideoSyncDoneEvent(
                    session_id=session_id or event.session_id,
                    frame_count=timeline.frame_index,
                    total_duration_ms=total_duration_ms,
                )
                yield event
                return

        yield VideoSyncErrorEvent(message="Speak stream ended without a completion event.")

    async def aclose(self) -> None:
        await self._client.aclose()