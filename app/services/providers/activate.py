"""Hot-reload LLM / TTS / video pipelines after RunPod wiring — no restart required."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI

from app.core.config import Settings

logger = logging.getLogger(__name__)


async def activate_provider_stack(app: FastAPI, settings: Settings) -> dict[str, Any]:
    """Swap live pipeline clients to match current settings."""
    llm = getattr(app.state, "llm_pipeline", None)
    tts = getattr(app.state, "tts_pipeline", None)
    video = getattr(app.state, "video_pipeline", None)
    probe = getattr(app.state, "provider_probe", None)

    if llm is not None and hasattr(llm, "reconfigure"):
        await llm.reconfigure(settings)
    if tts is not None and hasattr(tts, "reconfigure"):
        await tts.reconfigure(settings)
    if video is not None and hasattr(video, "reconfigure"):
        await video.reconfigure(settings)
    if probe is not None and hasattr(probe, "reconfigure"):
        await probe.reconfigure(settings)

    app.state.settings = settings
    report = {
        "activated": True,
        "llm": settings.llm_provider,
        "tts": settings.tts_provider,
        "video": settings.video_provider,
        "llm_base_url": settings.llm_base_url,
        "tts_base_url": settings.tts_base_url,
        "video_base_url": settings.video_base_url,
    }
    logger.info(
        "Provider stack activated — llm=%s tts=%s video=%s",
        settings.llm_provider,
        settings.tts_provider,
        settings.video_provider,
    )
    return report
