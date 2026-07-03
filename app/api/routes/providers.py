from fastapi import APIRouter, HTTPException, Request, status

from app.models.providers import ProviderStatus, ProvidersStatusResponse
from app.services.providers.probe import ProviderProbeService

router = APIRouter(prefix="/providers", tags=["providers"])


def _probe_service(request: Request) -> ProviderProbeService:
    return request.app.state.provider_probe


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