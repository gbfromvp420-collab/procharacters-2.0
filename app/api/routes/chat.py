import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.api.sse import format_sse
from app.models.llm import ChatRequest, StreamErrorEvent
from app.models.tts import TTSErrorEvent
from app.models.video import VideoSyncErrorEvent
from app.services.llm.pipeline import LLMStreamPipeline
from app.services.tts.pipeline import TTSStreamPipeline
from app.services.video.pipeline import VideoSyncPipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


async def _speak_event_stream(
    llm_pipeline: LLMStreamPipeline,
    tts_pipeline: TTSStreamPipeline,
    payload: ChatRequest,
) -> AsyncIterator[str]:
    try:
        llm_events = llm_pipeline.stream_completion(
            messages=payload.messages,
            session_id=payload.session_id,
            max_tokens=payload.max_tokens,
            temperature=payload.temperature,
        )
        async for event in tts_pipeline.stream_from_llm_events(
            llm_events,
            session_id=payload.session_id,
        ):
            yield format_sse(event)
    except Exception as exc:
        logger.exception("Unhandled chat/speak stream error")
        yield format_sse(StreamErrorEvent(message=str(exc)))
        yield format_sse(TTSErrorEvent(message=str(exc)))


async def _perform_event_stream(
    llm_pipeline: LLMStreamPipeline,
    tts_pipeline: TTSStreamPipeline,
    video_pipeline: VideoSyncPipeline,
    payload: ChatRequest,
    *,
    session_manager=None,
) -> AsyncIterator[str]:
    bridge = None
    initial_audio_cursor_ms = 0
    if payload.session_id and session_manager is not None:
        bridge = session_manager.get_media_bridge(payload.session_id)
        if bridge is not None:
            await bridge.begin_stream()
            initial_audio_cursor_ms = bridge.audio_timeline_ms

    try:
        llm_events = llm_pipeline.stream_completion(
            messages=payload.messages,
            session_id=payload.session_id,
            max_tokens=payload.max_tokens,
            temperature=payload.temperature,
        )
        speak_events = tts_pipeline.stream_from_llm_events(
            llm_events,
            session_id=payload.session_id,
        )
        async for event in video_pipeline.stream_from_speak_events(
            speak_events,
            session_id=payload.session_id,
            initial_audio_cursor_ms=initial_audio_cursor_ms,
            # initial_frame_index defaults to 0 (pts continuity driven by audio_cursor_ms)
        ):
            if bridge is not None:
                await bridge.ingest_event(event)
            yield format_sse(event)
    except Exception as exc:
        logger.exception("Unhandled chat/perform stream error")
        yield format_sse(StreamErrorEvent(message=str(exc)))
        yield format_sse(TTSErrorEvent(message=str(exc)))
        yield format_sse(VideoSyncErrorEvent(message=str(exc)))


@router.post(
    "/perform",
    summary="Full companion pipeline: LLM + TTS + MuseTalk (SSE; feeds WebRTC when session_id is set)",
    response_class=StreamingResponse,
)
async def perform(request: Request, payload: ChatRequest) -> StreamingResponse:
    llm_pipeline: LLMStreamPipeline = request.app.state.llm_pipeline
    tts_pipeline: TTSStreamPipeline = request.app.state.tts_pipeline
    video_pipeline: VideoSyncPipeline = request.app.state.video_pipeline

    session_manager = request.app.state.session_manager

    return StreamingResponse(
        _perform_event_stream(
            llm_pipeline,
            tts_pipeline,
            video_pipeline,
            payload,
            session_manager=session_manager,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-LLM-Provider": llm_pipeline.provider,
            "X-LLM-Model": llm_pipeline.model,
            "X-TTS-Provider": tts_pipeline.provider,
            "X-TTS-Voice": tts_pipeline.voice,
            "X-Video-Provider": video_pipeline.provider,
            "X-Video-Avatar": video_pipeline.avatar_id,
            "X-Video-FPS": str(video_pipeline.fps),
        },
    )


@router.post(
    "/speak",
    summary="Stream LLM tokens and TTS audio chunks in one SSE session",
    response_class=StreamingResponse,
)
async def speak(request: Request, payload: ChatRequest) -> StreamingResponse:
    llm_pipeline: LLMStreamPipeline = request.app.state.llm_pipeline
    tts_pipeline: TTSStreamPipeline = request.app.state.tts_pipeline

    return StreamingResponse(
        _speak_event_stream(llm_pipeline, tts_pipeline, payload),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-LLM-Provider": llm_pipeline.provider,
            "X-LLM-Model": llm_pipeline.model,
            "X-TTS-Provider": tts_pipeline.provider,
            "X-TTS-Voice": tts_pipeline.voice,
        },
    )