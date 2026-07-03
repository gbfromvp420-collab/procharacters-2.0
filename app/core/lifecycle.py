import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import Settings, get_settings
from app.services.companion.store import SessionCompanionStore
from app.services.llm.pipeline import LLMStreamPipeline
from app.services.providers.probe import ProviderProbeService
from app.services.tts.pipeline import TTSStreamPipeline
from app.services.video.pipeline import VideoSyncPipeline
from app.services.webrtc.session_manager import WebRTCSessionManager

logger = logging.getLogger(__name__)

_PRUNE_INTERVAL_SECONDS = 3600


async def _companion_prune_loop(
    companion_store: SessionCompanionStore,
    ttl_hours: int,
) -> None:
    while True:
        await asyncio.sleep(_PRUNE_INTERVAL_SECONDS)
        removed = companion_store.prune_stale(ttl_hours)
        if removed:
            logger.info("Pruned %d stale companion session(s)", removed)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = get_settings()
    companion_store = SessionCompanionStore(settings=settings)
    session_manager = WebRTCSessionManager(
        settings=settings,
        companion_store=companion_store,
    )
    llm_pipeline = LLMStreamPipeline(settings=settings)
    tts_pipeline = TTSStreamPipeline(settings=settings)
    video_pipeline = VideoSyncPipeline(settings=settings)
    provider_probe = ProviderProbeService(settings=settings)

    app.state.settings = settings
    app.state.companion_store = companion_store
    app.state.session_manager = session_manager
    app.state.llm_pipeline = llm_pipeline
    app.state.tts_pipeline = tts_pipeline
    app.state.video_pipeline = video_pipeline
    app.state.provider_probe = provider_probe

    prune_task: asyncio.Task[None] | None = None
    if settings.companion_persist_enabled:
        prune_task = asyncio.create_task(
            _companion_prune_loop(
                companion_store,
                settings.companion_session_ttl_hours,
            )
        )

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
    if prune_task is not None:
        prune_task.cancel()
        try:
            await prune_task
        except asyncio.CancelledError:
            pass
    companion_store.save_all()
    await provider_probe.aclose()
    await video_pipeline.aclose()
    await tts_pipeline.aclose()
    await llm_pipeline.aclose()
    await session_manager.close_all()
    logger.info("Shutdown complete")