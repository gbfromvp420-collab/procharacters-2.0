import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from app.api.sse import format_sse
from app.models.llm import (
    ChatMessage,
    ChatModesResponse,
    ChatRequest,
    StreamDoneEvent,
    StreamErrorEvent,
    StreamTokenEvent,
)
from app.models.tts import TTSErrorEvent
from app.models.video import VideoSyncErrorEvent
from app.services.companion.store import SessionCompanionStore
from app.services.llm.pipeline import LLMStreamPipeline
from app.services.observability.metrics import MetricsCollector
from app.services.tts.pipeline import TTSStreamPipeline
from app.services.providers.gate import check_providers_ready
from app.services.video.pipeline import VideoSyncPipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


def _last_user_message(messages: list[ChatMessage]) -> ChatMessage | None:
    for msg in reversed(messages):
        if msg.role == "user":
            return msg
    return None


def _sse_resilience_headers(
    session_id: str | None,
    *,
    session_manager,
    companion_store: SessionCompanionStore,
) -> dict[str, str]:
    """Headers for SSE clients to detect WebRTC bond and stored companion memory."""
    if not session_id:
        return {}
    bonded = session_manager.get_session(session_id) is not None
    has_memory = len(companion_store.get_messages(session_id)) > 0
    return {
        "X-Session-Bond": "true" if bonded else "false",
        "X-Memory-Summary-Present": "true" if has_memory else "false",
    }


def _resolve_chat_context(
    payload: ChatRequest,
    companion_store: SessionCompanionStore | None,
) -> tuple[list[ChatMessage], str | None, str | None]:
    """Build LLM messages and resolve per-session voice/avatar overrides."""
    voice: str | None = None
    avatar_id: str | None = None

    if payload.session_id and companion_store is not None:
        cfg = companion_store.get_config(payload.session_id)
        voice = cfg["voice"]
        avatar_id = cfg["avatar_id"]
        llm_messages = companion_store.build_llm_messages(
            payload.session_id,
            payload.messages,
            use_memory=payload.use_memory,
        )
        return llm_messages, voice, avatar_id

    return payload.messages, voice, avatar_id


async def _speak_event_stream(
    llm_pipeline: LLMStreamPipeline,
    tts_pipeline: TTSStreamPipeline,
    payload: ChatRequest,
    *,
    companion_store: SessionCompanionStore | None = None,
    metrics: MetricsCollector | None = None,
) -> AsyncIterator[str]:
    llm_messages, voice, _avatar_id = _resolve_chat_context(payload, companion_store)
    user_turn = _last_user_message(payload.messages)
    assistant_parts: list[str] = []
    persist_turn = (
        payload.session_id is not None
        and companion_store is not None
        and payload.use_memory
        and user_turn is not None
    )

    try:
        llm_events = llm_pipeline.stream_completion(
            messages=llm_messages,
            session_id=payload.session_id,
            max_tokens=payload.max_tokens,
            temperature=payload.temperature,
        )
        async for event in tts_pipeline.stream_from_llm_events(
            llm_events,
            session_id=payload.session_id,
            voice=voice,
        ):
            if isinstance(event, StreamTokenEvent):
                assistant_parts.append(event.content)
                if metrics is not None:
                    metrics.increment_tokens_streamed()
            if (
                persist_turn
                and isinstance(event, StreamDoneEvent)
                and assistant_parts
            ):
                companion_store.append_turn(
                    payload.session_id,
                    user_turn,
                    ChatMessage(role="assistant", content="".join(assistant_parts)),
                )
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
    companion_store: SessionCompanionStore | None = None,
    metrics: MetricsCollector | None = None,
) -> AsyncIterator[str]:
    bridge = None
    initial_audio_cursor_ms = 0
    if payload.session_id and session_manager is not None:
        bridge = session_manager.get_media_bridge(payload.session_id)
        if bridge is not None:
            await bridge.begin_stream()
            initial_audio_cursor_ms = bridge.audio_timeline_ms

    llm_messages, voice, avatar_id = _resolve_chat_context(payload, companion_store)
    user_turn = _last_user_message(payload.messages)
    assistant_parts: list[str] = []
    persist_turn = (
        payload.session_id is not None
        and companion_store is not None
        and payload.use_memory
        and user_turn is not None
    )

    try:
        llm_events = llm_pipeline.stream_completion(
            messages=llm_messages,
            session_id=payload.session_id,
            max_tokens=payload.max_tokens,
            temperature=payload.temperature,
        )
        speak_events = tts_pipeline.stream_from_llm_events(
            llm_events,
            session_id=payload.session_id,
            voice=voice,
        )
        async for event in video_pipeline.stream_from_speak_events(
            speak_events,
            session_id=payload.session_id,
            avatar_id=avatar_id,
            initial_audio_cursor_ms=initial_audio_cursor_ms,
            # initial_frame_index defaults to 0 (pts continuity driven by audio_cursor_ms)
        ):
            if isinstance(event, StreamTokenEvent):
                assistant_parts.append(event.content)
                if metrics is not None:
                    metrics.increment_tokens_streamed()
            if bridge is not None:
                await bridge.ingest_event(event)
            if (
                persist_turn
                and isinstance(event, StreamDoneEvent)
                and assistant_parts
            ):
                companion_store.append_turn(
                    payload.session_id,
                    user_turn,
                    ChatMessage(role="assistant", content="".join(assistant_parts)),
                )
            yield format_sse(event)
    except Exception as exc:
        logger.exception("Unhandled chat/perform stream error")
        yield format_sse(StreamErrorEvent(message=str(exc)))
        yield format_sse(TTSErrorEvent(message=str(exc)))
        yield format_sse(VideoSyncErrorEvent(message=str(exc)))


@router.get(
    "/modes",
    response_model=ChatModesResponse,
    summary="Report available chat transport modes (WebRTC + SSE fallbacks)",
)
async def chat_modes() -> ChatModesResponse:
    return ChatModesResponse(webrtc=True, sse_perform=True, sse_speak=True)


@router.post(
    "/perform",
    summary="Full companion pipeline: LLM + TTS + MuseTalk (SSE; feeds WebRTC when session_id is set)",
    response_class=StreamingResponse,
)
async def perform(request: Request, payload: ChatRequest) -> StreamingResponse:
    ok, gate_message = await check_providers_ready(request.app, ["llm", "tts", "video"])
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=gate_message,
        )

    llm_pipeline: LLMStreamPipeline = request.app.state.llm_pipeline
    tts_pipeline: TTSStreamPipeline = request.app.state.tts_pipeline
    video_pipeline: VideoSyncPipeline = request.app.state.video_pipeline

    session_manager = request.app.state.session_manager
    companion_store: SessionCompanionStore = request.app.state.companion_store
    metrics: MetricsCollector = request.app.state.metrics
    metrics.increment_perform_requests()
    session_voice = None
    session_avatar = None
    if payload.session_id:
        companion_store.touch(payload.session_id)
        cfg = companion_store.get_config(payload.session_id)
        session_voice = cfg["voice"]
        session_avatar = cfg["avatar_id"]

    perform_headers: dict[str, str] = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-LLM-Provider": llm_pipeline.provider,
        "X-LLM-Model": llm_pipeline.model,
        "X-TTS-Provider": tts_pipeline.provider,
        "X-TTS-Voice": session_voice or tts_pipeline.voice,
        "X-Video-Provider": video_pipeline.provider,
        "X-Video-Avatar": session_avatar or video_pipeline.avatar_id,
        "X-Video-FPS": str(video_pipeline.fps),
    }
    perform_headers.update(
        _sse_resilience_headers(
            payload.session_id,
            session_manager=session_manager,
            companion_store=companion_store,
        )
    )

    return StreamingResponse(
        _perform_event_stream(
            llm_pipeline,
            tts_pipeline,
            video_pipeline,
            payload,
            session_manager=session_manager,
            companion_store=companion_store,
            metrics=metrics,
        ),
        media_type="text/event-stream",
        headers=perform_headers,
    )


@router.post(
    "/speak",
    summary="Stream LLM tokens and TTS audio chunks in one SSE session",
    response_class=StreamingResponse,
)
async def speak(request: Request, payload: ChatRequest) -> StreamingResponse:
    ok, gate_message = await check_providers_ready(request.app, ["llm", "tts"])
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=gate_message,
        )

    llm_pipeline: LLMStreamPipeline = request.app.state.llm_pipeline
    tts_pipeline: TTSStreamPipeline = request.app.state.tts_pipeline
    companion_store: SessionCompanionStore = request.app.state.companion_store
    metrics: MetricsCollector = request.app.state.metrics
    metrics.increment_speak_requests()
    session_voice = None
    if payload.session_id:
        companion_store.touch(payload.session_id)
        session_voice = companion_store.get_config(payload.session_id)["voice"]

    return StreamingResponse(
        _speak_event_stream(
            llm_pipeline,
            tts_pipeline,
            payload,
            companion_store=companion_store,
            metrics=metrics,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-LLM-Provider": llm_pipeline.provider,
            "X-LLM-Model": llm_pipeline.model,
            "X-TTS-Provider": tts_pipeline.provider,
            "X-TTS-Voice": session_voice or tts_pipeline.voice,
        },
    )