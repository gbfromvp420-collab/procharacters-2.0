import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.api.sse import format_sse
from app.models.tts import AudioChunkEvent
from app.models.video import VideoSyncDoneEvent, VideoSyncErrorEvent, VideoSyncRequest
from app.services.video.pipeline import VideoSyncPipeline
from app.services.video.sync import SyncTimeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/video", tags=["video"])


async def _sync_event_stream(
    pipeline: VideoSyncPipeline,
    payload: VideoSyncRequest,
) -> AsyncIterator[str]:
    timeline = SyncTimeline(fps=pipeline.fps)
    audio_chunk = AudioChunkEvent(
        chunk_index=payload.audio_chunk_index,
        text="",
        audio_b64=payload.audio_b64,
        sample_rate=payload.sample_rate,
        channels=payload.channels,
        duration_ms=payload.duration_ms,
        session_id=payload.session_id,
    )

    try:
        async for event in pipeline.stream_from_audio_chunk(
            audio_chunk,
            timeline=timeline,
            avatar_id=payload.avatar_id,
        ):
            yield format_sse(event)

        yield format_sse(
            VideoSyncDoneEvent(
                session_id=payload.session_id,
                frame_count=timeline.frame_index,
                total_duration_ms=payload.duration_ms,
            )
        )
    except Exception as exc:
        logger.exception("Unhandled video sync stream error")
        yield format_sse(VideoSyncErrorEvent(message=str(exc)))


@router.post(
    "/sync",
    summary="Generate MuseTalk frames synchronized to an audio chunk (SSE)",
    response_class=StreamingResponse,
)
async def sync_video(request: Request, payload: VideoSyncRequest) -> StreamingResponse:
    pipeline: VideoSyncPipeline = request.app.state.video_pipeline

    return StreamingResponse(
        _sync_event_stream(pipeline, payload),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Video-Provider": pipeline.provider,
            "X-Video-Avatar": pipeline.avatar_id,
            "X-Video-FPS": str(pipeline.fps),
        },
    )


@router.get("/status", summary="Video sync pipeline configuration")
async def video_status(request: Request) -> dict[str, str | int]:
    pipeline: VideoSyncPipeline = request.app.state.video_pipeline
    settings = request.app.state.settings

    return {
        "provider": pipeline.provider,
        "avatar_id": pipeline.avatar_id,
        "fps": pipeline.fps,
        "width": settings.video_width,
        "height": settings.video_height,
    }