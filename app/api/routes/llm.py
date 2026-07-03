import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.api.sse import format_sse
from app.models.llm import ChatRequest, StreamErrorEvent
from app.services.llm.pipeline import LLMStreamPipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/llm", tags=["llm"])


async def _chat_event_stream(
    pipeline: LLMStreamPipeline,
    payload: ChatRequest,
) -> AsyncIterator[str]:
    try:
        async for event in pipeline.stream_completion(
            messages=payload.messages,
            session_id=payload.session_id,
            max_tokens=payload.max_tokens,
            temperature=payload.temperature,
        ):
            yield format_sse(event)
    except Exception as exc:
        logger.exception("Unhandled LLM stream error")
        yield format_sse(StreamErrorEvent(message=str(exc)))


@router.post(
    "/chat",
    summary="Stream a chat completion token-by-token (SSE)",
    response_class=StreamingResponse,
)
async def stream_chat(request: Request, payload: ChatRequest) -> StreamingResponse:
    pipeline: LLMStreamPipeline = request.app.state.llm_pipeline

    return StreamingResponse(
        _chat_event_stream(pipeline, payload),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-LLM-Provider": pipeline.provider,
            "X-LLM-Model": pipeline.model,
        },
    )


@router.get(
    "/status",
    summary="LLM pipeline configuration",
)
async def llm_status(request: Request) -> dict[str, str | int | float]:
    pipeline: LLMStreamPipeline = request.app.state.llm_pipeline
    settings = request.app.state.settings

    return {
        "provider": pipeline.provider,
        "model": pipeline.model,
        "max_tokens": settings.llm_max_tokens,
        "temperature": settings.llm_temperature,
    }