import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.api.sse import format_sse
from app.models.tts import SynthesizeRequest, TTSErrorEvent
from app.services.tts.pipeline import TTSStreamPipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tts", tags=["tts"])


async def _synthesize_event_stream(
    pipeline: TTSStreamPipeline,
    payload: SynthesizeRequest,
) -> AsyncIterator[str]:
    try:
        async for event in pipeline.stream_from_text(
            payload.text,
            session_id=payload.session_id,
            voice=payload.voice,
        ):
            yield format_sse(event)
    except Exception as exc:
        logger.exception("Unhandled TTS stream error")
        yield format_sse(TTSErrorEvent(message=str(exc)))


@router.post(
    "/synthesize",
    summary="Synthesize text into chunked PCM audio (SSE)",
    response_class=StreamingResponse,
)
async def synthesize(request: Request, payload: SynthesizeRequest) -> StreamingResponse:
    pipeline: TTSStreamPipeline = request.app.state.tts_pipeline

    return StreamingResponse(
        _synthesize_event_stream(pipeline, payload),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-TTS-Provider": pipeline.provider,
            "X-TTS-Voice": pipeline.voice,
        },
    )


@router.get("/status", summary="TTS pipeline configuration")
async def tts_status(request: Request) -> dict[str, str | int]:
    pipeline: TTSStreamPipeline = request.app.state.tts_pipeline
    settings = request.app.state.settings

    return {
        "provider": pipeline.provider,
        "voice": pipeline.voice,
        "sample_rate": settings.tts_sample_rate,
        "channels": settings.tts_channels,
        "chunk_min_chars": settings.tts_chunk_min_chars,
        "chunk_max_chars": settings.tts_chunk_max_chars,
    }