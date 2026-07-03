from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.models.health import LivenessResponse, ReadinessResponse
from app.services.deploy.readiness import evaluate_readiness

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(request: Request) -> dict:
    settings = get_settings()
    session_manager = request.app.state.session_manager
    llm_pipeline = request.app.state.llm_pipeline
    tts_pipeline = request.app.state.tts_pipeline
    video_pipeline = request.app.state.video_pipeline
    provider_probe = request.app.state.provider_probe
    providers_summary = await provider_probe.get_providers_summary(timeout_seconds=2.0)
    body: dict = {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "deployment_phase": settings.deployment_phase,
        "active_webrtc_sessions": session_manager.active_session_count,
        "active_sessions": session_manager.list_session_ids(),
        # Richer per-session state (conn/ice) to aid resume/reconnect without breaking API consumers
        "webrtc_sessions": session_manager.list_sessions_with_details(),
        "llm_provider": llm_pipeline.provider,
        "llm_model": llm_pipeline.model,
        "tts_provider": tts_pipeline.provider,
        "tts_voice": tts_pipeline.voice,
        "video_provider": video_pipeline.provider,
        "video_avatar_id": video_pipeline.avatar_id,
        "video_fps": video_pipeline.fps,
        "mock_realistic": settings.mock_realistic,
        "providers_summary": providers_summary,
    }

    metrics = getattr(request.app.state, "metrics", None)
    if metrics is not None:
        summary = getattr(metrics, "metrics_summary", None)
        if callable(summary):
            body["metrics_summary"] = summary()
        elif hasattr(metrics, "snapshot"):
            body["metrics_summary"] = metrics.snapshot()

    return body


@router.get(
    "/health/live",
    response_model=LivenessResponse,
    summary="Liveness probe — process is up",
)
async def liveness_probe() -> LivenessResponse:
    settings = get_settings()
    return LivenessResponse(
        service=settings.app_name,
        version=settings.app_version,
        deployment_phase=settings.deployment_phase,
    )


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    summary="Readiness probe — persistence writable and providers gate satisfied",
)
async def readiness_probe(request: Request) -> JSONResponse:
    settings = get_settings()
    ready, checks = await evaluate_readiness(request)
    payload = ReadinessResponse(
        status="ready" if ready else "not_ready",
        service=settings.app_name,
        version=settings.app_version,
        deployment_phase=settings.deployment_phase,
        checks=checks,
    )
    return JSONResponse(
        status_code=status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE,
        content=payload.model_dump(),
    )