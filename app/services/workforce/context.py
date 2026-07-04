"""Execution context passed to workforce skill executors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.config import Settings
    from app.services.companion.store import SessionCompanionStore
    from app.services.kgc.audit import AuditLog
    from app.services.kgc.policies import KGCPolicies
    from app.services.observability.metrics import MetricsCollector
    from app.services.providers.probe import ProviderProbeService
    from app.services.webrtc.session_manager import WebRTCSessionManager
    from app.services.workforce.lounge import AgentLounge
    from app.services.workforce.character_forge import CharacterForge
    from app.services.workforce.live_stage import LiveStage
    from app.services.workforce.crown_completion import CrownCompletion
    from app.services.workforce.sovereign_scale import SovereignScale
    from app.services.workforce.revenue import RevenueForge
    from app.services.workforce.theater import AgentTheater


@dataclass
class WorkforceContext:
    """App services available during subagent task execution."""

    settings: Settings
    companion_store: SessionCompanionStore
    session_manager: WebRTCSessionManager
    metrics: MetricsCollector
    provider_probe: ProviderProbeService
    kgc_policies: KGCPolicies
    kgc_audit: AuditLog
    agent_theater: AgentTheater
    agent_lounge: AgentLounge
    revenue_forge: RevenueForge
    character_forge: CharacterForge
    live_stage: LiveStage
    sovereign_scale: SovereignScale
    crown_completion: CrownCompletion