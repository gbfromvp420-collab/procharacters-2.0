import json
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.models.llm import ChatMessage
from app.models.providers import (
    ProviderForgeResponse,
    ProviderStatus,
    ProvidersStatusResponse,
)
from app.services.llm.client import MockLLMClient
from app.services.providers.forge import ProviderContractForge
from app.services.providers.local_stubs import local_stub_report, stub_runtime_settings
from app.services.providers.probe import ProviderProbeService
from app.services.tts.audio import encode_pcm_b64
from app.services.tts.client import MockTTSClient
from app.services.video.client import MockMuseTalkClient
from app.services.video.sync import SyncTimeline

router = APIRouter(prefix="/providers", tags=["providers"])


def _probe_service(request: Request) -> ProviderProbeService:
    return request.app.state.provider_probe


def _forge_service(request: Request) -> ProviderContractForge:
    return ProviderContractForge(
        request.app.state.settings,
        probe=_probe_service(request),
    )


@router.get(
    "/status",
    response_model=ProvidersStatusResponse,
    summary="Probe all configured providers (LLM, TTS, video)",
)
async def get_all_provider_status(request: Request) -> ProvidersStatusResponse:
    probe = _probe_service(request)
    result = await probe.probe_all()
    return ProvidersStatusResponse(**result)


@router.get(
    "/status/{name}",
    response_model=ProviderStatus,
    summary="Probe a single provider: llm, tts, or video",
)
async def get_provider_status(request: Request, name: str) -> ProviderStatus:
    probe = _probe_service(request)
    normalized = name.lower().strip()
    if normalized == "llm":
        return await probe.probe_llm()
    if normalized == "tts":
        return await probe.probe_tts()
    if normalized == "video":
        return await probe.probe_video()
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Unknown provider name. Use llm, tts, or video.",
    )


@router.get(
    "/forge",
    response_model=ProviderForgeResponse,
    summary="Contract forge report — probe + spec compliance (optional live smoke)",
)
async def get_provider_forge_report(
    request: Request,
    live_smoke: bool = Query(
        default=False,
        description="When true, runs minimal real requests against remote providers.",
    ),
) -> ProviderForgeResponse:
    forge = _forge_service(request)
    return await forge.evaluate_all(live_smoke=live_smoke)


@router.post(
    "/forge/smoke",
    response_model=ProviderForgeResponse,
    summary="Run live contract smoke against configured remote providers",
)
async def run_provider_forge_smoke(request: Request) -> ProviderForgeResponse:
    forge = _forge_service(request)
    return await forge.evaluate_all(live_smoke=True)


class LocalChatRequest(BaseModel):
    model: str | None = None
    messages: list[dict[str, Any]] = Field(default_factory=list)
    stream: bool = True
    max_tokens: int = 64
    temperature: float = 0.7


class LocalSynthesizeRequest(BaseModel):
    text: str = ""
    voice: str | None = None
    format: str = "pcm_s16le"
    sample_rate: int | None = None
    channels: int | None = None


class LocalGenerateRequest(BaseModel):
    audio_b64: str = ""
    sample_rate: int = 24000
    channels: int = 1
    duration_ms: int = 200
    avatar_id: str = "default"
    fps: int | None = None
    start_pts_ms: int = 0
    start_frame_index: int = 0


@router.get(
    "/local",
    summary="Local HTTP contract stub URLs for Stage 1 (no RunPod required)",
)
@router.get("/local/health")
@router.get("/local/v1/health")
async def local_contract_stub_info(request: Request) -> dict[str, Any]:
    return local_stub_report(request)


@router.get("/local/v1/models")
async def local_openai_models(request: Request) -> dict[str, Any]:
    settings = request.app.state.settings
    return {
        "object": "list",
        "data": [
            {
                "id": settings.llm_model,
                "object": "model",
                "owned_by": "procharacters-local-stubs",
            }
        ],
    }


@router.post(
    "/local/v1/chat/completions",
    summary="OpenAI-compatible chat completions stub (Innovation Lane 1)",
)
async def local_chat_completions(request: Request, body: LocalChatRequest) -> Any:
    settings = stub_runtime_settings(request.app.state.settings)
    client = MockLLMClient(settings)
    messages: list[ChatMessage] = []
    for item in body.messages:
        role = str(item.get("role", "user"))
        if role not in {"system", "user", "assistant"}:
            role = "user"
        messages.append(ChatMessage(role=role, content=str(item.get("content", ""))))
    if not messages:
        messages.append(ChatMessage(role="user", content="Hello"))

    async def _token_stream():
        async for token in client.stream_tokens(
            messages,
            max_tokens=body.max_tokens,
            temperature=body.temperature,
        ):
            chunk = {
                "id": "local-stub",
                "object": "chat.completion.chunk",
                "choices": [
                    {
                        "index": 0,
                        "delta": {"content": token},
                        "finish_reason": None,
                    }
                ],
            }
            yield f"data: {json.dumps(chunk)}\n\n"
        yield "data: [DONE]\n\n"

    if body.stream:
        return StreamingResponse(_token_stream(), media_type="text/event-stream")

    tokens: list[str] = []
    async for token in client.stream_tokens(
        messages,
        max_tokens=body.max_tokens,
        temperature=body.temperature,
    ):
        tokens.append(token)
    text = "".join(tokens)
    return JSONResponse(
        {
            "id": "local-stub",
            "object": "chat.completion",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": text},
                    "finish_reason": "stop",
                }
            ],
        }
    )


@router.post(
    "/local/synthesize",
    summary="TTS /synthesize contract stub (Innovation Lane 1)",
)
async def local_synthesize(request: Request, body: LocalSynthesizeRequest) -> dict[str, Any]:
    settings = stub_runtime_settings(request.app.state.settings)
    client = MockTTSClient(settings)
    audio = await client.synthesize(body.text or "ok", voice=body.voice)
    return {
        "audio_b64": encode_pcm_b64(audio.pcm_bytes),
        "sample_rate": audio.sample_rate,
        "channels": audio.channels,
    }


@router.post(
    "/local/generate",
    summary="Video /generate contract stub (Innovation Lane 1)",
)
async def local_generate(request: Request, body: LocalGenerateRequest) -> dict[str, Any]:
    settings = stub_runtime_settings(request.app.state.settings)
    fps = body.fps or settings.video_fps
    timeline = SyncTimeline(
        fps=fps,
        start_audio_ms=body.start_pts_ms,
        start_frame_index=body.start_frame_index,
    )
    client = MockMuseTalkClient(settings)
    result = await client.generate_frames(
        audio_b64=body.audio_b64,
        sample_rate=body.sample_rate,
        channels=body.channels,
        duration_ms=body.duration_ms,
        timeline=timeline,
        avatar_id=body.avatar_id or settings.video_avatar_id,
    )
    return {
        "frames": [
            {
                "frame_index": frame.frame_index,
                "pts_ms": frame.pts_ms,
                "frame_b64": frame.frame_b64,
            }
            for frame in result.frames
        ],
        "width": result.width,
        "height": result.height,
    }