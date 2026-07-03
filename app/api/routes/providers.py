from fastapi import APIRouter, HTTPException, Query, Request, status

from app.models.providers import (
    ProviderForgeResponse,
    ProviderStatus,
    ProvidersStatusResponse,
)
from app.services.providers.forge import ProviderContractForge
from app.services.providers.probe import ProviderProbeService

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