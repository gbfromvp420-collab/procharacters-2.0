import asyncio
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import Settings, get_settings
from app.services.companion.store import SessionCompanionStore
from app.services.kgc.audit import get_audit_log
from app.services.kgc.policies import KGCPolicies
from app.services.observability.metrics import MetricsCollector
from app.services.llm.pipeline import LLMStreamPipeline
from app.services.providers.probe import ProviderProbeService
from app.services.tts.pipeline import TTSStreamPipeline
from app.services.video.pipeline import VideoSyncPipeline
from app.services.webrtc.session_manager import WebRTCSessionManager
from app.services.workforce.lounge import AgentLounge
from app.services.workforce.character_forge import CharacterForge
from app.services.workforce.live_stage import LiveStage
from app.services.workforce.crown_completion import CrownCompletion
from app.services.workforce.innovation import InnovationLanes
from app.services.workforce.swarm_payout import SwarmPayout
from app.services.workforce.sovereign_scale import SovereignScale
from app.services.workforce.revenue import RevenueForge
from app.services.workforce.theater import AgentTheater

logger = logging.getLogger(__name__)

_PRUNE_INTERVAL_SECONDS = 3600


async def _companion_prune_loop(
    companion_store: SessionCompanionStore,
    ttl_hours: int,
    kgc_policies: KGCPolicies,
) -> None:
    from app.services.kgc.audit import log_action

    while True:
        await asyncio.sleep(_PRUNE_INTERVAL_SECONDS)
        if not kgc_policies.is_auto_prune_enabled():
            continue
        removed = companion_store.prune_stale(ttl_hours)
        if removed:
            logger.info("Pruned %d stale companion session(s)", removed)
            log_action("fleet.prune", f"auto_prune removed={removed} ttl_hours={ttl_hours}")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = get_settings()
    metrics = MetricsCollector()
    started_at_monotonic = time.monotonic()
    kgc_policies = KGCPolicies(path=settings.kgc_policies_path)
    kgc_audit = get_audit_log()
    companion_store = SessionCompanionStore(
        settings=settings,
        metrics=metrics,
        kgc_policies=kgc_policies,
    )
    session_manager = WebRTCSessionManager(
        settings=settings,
        companion_store=companion_store,
    )
    llm_pipeline = LLMStreamPipeline(settings=settings)
    tts_pipeline = TTSStreamPipeline(settings=settings)
    video_pipeline = VideoSyncPipeline(settings=settings)
    provider_probe = ProviderProbeService(settings=settings)
    agent_theater = AgentTheater()
    agent_lounge = AgentLounge(
        lounge_path=settings.agent_lounge_path,
        comments_path=settings.agent_lounge_comments_path,
    )
    revenue_forge = RevenueForge(
        schema_path=settings.revenue_schema_path,
        ledger_path=settings.revenue_ledger_path,
    )
    character_forge = CharacterForge(
        schema_path=settings.character_forge_schema_path,
        registry_path=settings.character_forge_registry_path,
        residuals_path=settings.character_forge_residuals_path,
        companion_avatars=settings.companion_avatars,
    )
    live_stage = LiveStage(
        schema_path=settings.live_stage_schema_path,
        sessions_path=settings.live_stage_sessions_path,
        billing_path=settings.live_stage_billing_path,
    )
    sovereign_scale = SovereignScale(
        schema_path=settings.sovereign_scale_schema_path,
        tenants_path=settings.sovereign_tenants_path,
        nodes_path=settings.sovereign_nodes_path,
    )
    crown_completion = CrownCompletion(
        schema_path=settings.crown_completion_schema_path,
        cosign_path=settings.crown_cosign_path,
        gifts_granted_path=settings.crown_gifts_granted_path,
        creative_sessions_path=settings.crown_creative_sessions_path,
    )
    swarm_payout = SwarmPayout(schema_path=settings.swarm_payout_schema_path)
    innovation_lanes = InnovationLanes(schema_path=settings.innovation_lanes_path)

    app.state.settings = settings
    app.state.metrics = metrics
    app.state.started_at_monotonic = started_at_monotonic
    app.state.kgc_policies = kgc_policies
    app.state.kgc_audit = kgc_audit
    app.state.companion_store = companion_store
    app.state.session_manager = session_manager
    app.state.llm_pipeline = llm_pipeline
    app.state.tts_pipeline = tts_pipeline
    app.state.video_pipeline = video_pipeline
    app.state.provider_probe = provider_probe
    app.state.agent_theater = agent_theater
    app.state.agent_lounge = agent_lounge
    app.state.revenue_forge = revenue_forge
    app.state.character_forge = character_forge
    app.state.live_stage = live_stage
    app.state.sovereign_scale = sovereign_scale
    app.state.crown_completion = crown_completion
    app.state.swarm_payout = swarm_payout
    app.state.innovation_lanes = innovation_lanes

    prune_task: asyncio.Task[None] | None = None
    if settings.companion_persist_enabled:
        prune_task = asyncio.create_task(
            _companion_prune_loop(
                companion_store,
                settings.companion_session_ttl_hours,
                kgc_policies,
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