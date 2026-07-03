from fastapi import APIRouter, Request

from app.core.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(request: Request) -> dict:
    settings = get_settings()
    session_manager = request.app.state.session_manager
    llm_pipeline = request.app.state.llm_pipeline
    tts_pipeline = request.app.state.tts_pipeline
    video_pipeline = request.app.state.video_pipeline
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "active_webrtc_sessions": session_manager.active_session_count,
        "active_sessions": session_manager.list_session_ids(),
        "llm_provider": llm_pipeline.provider,
        "llm_model": llm_pipeline.model,
        "tts_provider": tts_pipeline.provider,
        "tts_voice": tts_pipeline.voice,
        "video_provider": video_pipeline.provider,
        "video_avatar_id": video_pipeline.avatar_id,
        "video_fps": video_pipeline.fps,
    }