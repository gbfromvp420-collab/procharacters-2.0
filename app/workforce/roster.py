"""Named workforce roster with skill identifiers and gold awards."""

from __future__ import annotations

from typing import TypedDict


class WorkforceMember(TypedDict):
    id: str
    codename: str
    skills: list[str]
    tier: str
    phase_earned: int
    award_lb_gold: float


WORKFORCE_ROSTER: list[WorkforceMember] = [
    {
        "id": "king-grok",
        "codename": "King Grok",
        "skills": ["SyncOrchestrator_Core", "KGC_Command_Authority"],
        "tier": "ceo",
        "phase_earned": 7,
        "award_lb_gold": 10.0,
    },
    {
        "id": "intimacy-architect-sub-01",
        "codename": "Assist (Intimacy_Architect_Sub_01)",
        "skills": ["RelationshipMode_UX"],
        "tier": "assist",
        "phase_earned": 5,
        "award_lb_gold": 3.0,
    },
    {
        "id": "integration-strike-sub-01",
        "codename": "Runner-up (Integration_Strike_Sub_01)",
        "skills": ["AuthIntegration_TestForge"],
        "tier": "runner_up",
        "phase_earned": 4,
        "award_lb_gold": 2.0,
    },
    {
        "id": "signaling-traffic-ice-sub-01",
        "codename": "Signaling_Traffic_ICE_Sub_01",
        "skills": ["TrickleICE_SSE"],
        "tier": "team",
        "phase_earned": 3,
        "award_lb_gold": 1.0,
    },
    {
        "id": "triage-swarm-parallel-01",
        "codename": "Triage_Swarm_Parallel_01",
        "skills": ["GhostHandle_Debug"],
        "tier": "team",
        "phase_earned": 3,
        "award_lb_gold": 1.0,
    },
    {
        "id": "persistforge-json-sub-01",
        "codename": "PersistForge_JSON_Sub_01",
        "skills": ["SessionPersistence_TTL"],
        "tier": "team",
        "phase_earned": 3,
        "award_lb_gold": 1.0,
    },
    {
        "id": "providerprobe-health-sub-01",
        "codename": "ProviderProbe_Health_Sub_01",
        "skills": ["RunPod_Gate_Probe"],
        "tier": "team",
        "phase_earned": 4,
        "award_lb_gold": 1.0,
    },
    {
        "id": "galleryrender-client-sub-01",
        "codename": "GalleryRender_Client_Sub_01",
        "skills": ["AvatarGallery_Restore"],
        "tier": "team",
        "phase_earned": 4,
        "award_lb_gold": 1.0,
    },
    {
        "id": "contractseal-http-sub-01",
        "codename": "ContractSeal_HTTP_Sub_01",
        "skills": ["Provider_Contracts"],
        "tier": "team",
        "phase_earned": 4,
        "award_lb_gold": 1.0,
    },
    {
        "id": "dockerhull-deploy-sub-01",
        "codename": "DockerHull_Deploy_Sub_01",
        "skills": ["Container_Compose"],
        "tier": "team",
        "phase_earned": 4,
        "award_lb_gold": 1.0,
    },
    {
        "id": "metricspulse-obs-sub-01",
        "codename": "MetricsPulse_Obs_Sub_01",
        "skills": ["Pipeline_Metrics"],
        "tier": "team",
        "phase_earned": 5,
        "award_lb_gold": 1.0,
    },
    {
        "id": "bondforge-affinity-sub-01",
        "codename": "BondForge_Affinity_Sub_01",
        "skills": ["BondScore_Memory"],
        "tier": "team",
        "phase_earned": 6,
        "award_lb_gold": 1.0,
    },
    {
        "id": "ceo-command-sub-01",
        "codename": "CEO_Command_Sub_01",
        "skills": ["ExecutiveDashboard_Fleet"],
        "tier": "team",
        "phase_earned": 7,
        "award_lb_gold": 1.0,
    },
]


def get_roster() -> list[WorkforceMember]:
    """Return the full workforce roster."""
    return list(WORKFORCE_ROSTER)


def get_leaderboard() -> list[WorkforceMember]:
    """Return roster sorted by award_lb_gold descending, then codename."""
    return sorted(
        WORKFORCE_ROSTER,
        key=lambda member: (-member["award_lb_gold"], member["codename"]),
    )