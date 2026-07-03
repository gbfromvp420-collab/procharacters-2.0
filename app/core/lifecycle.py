import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import Settings, get_settings
from app.services.llm.pipeline import LLMStreamPipeline
from app.services.tts.pipeline import TTSStreamPipeline
from app.services.video.pipeline import VideoSyncPipeline
from app.services.webrtc.session_manager import WebRTCSessionManager

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = get_settings()
    session_manager = WebRTCSessionManager(settings=settings)
    llm_pipeline = LLMStreamPipeline(settings=settings)
    tts_pipeline = TTSStreamPipeline(settings=settings)
    video_pipeline = VideoSyncPipeline(settings=settings)

    app.state.settings = settings
    app.state.session_manager = session_manager
    app.state.llm_pipeline = llm_pipeline
    app.state.tts_pipeline = tts_pipeline
    app.state.video_pipeline = video_pipeline

    logger.info(
        "Starting %s v%s (llm=%s/%s, tts=%s/%s, video=%s/%s)",
        settings.app_name,
        settings.app_version,
        settings.llm_provider,
        settings.llm_model,
        settings.tts_provider,
        settings.tts_voice,
        settings.video_provider,
        settings.video_avatar_id,
    )
    yield
    await video_pipeline.aclose()
    await tts_pipeline.aclose()
    await llm_pipeline.aclose()
    await session_manager.close_all()
    logger.info("Shutdown complete")