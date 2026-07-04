from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class WorkforceMemberResponse(BaseModel):
    id: str
    codename: str
    skills: list[str]
    tier: str
    phase_earned: int
    award_lb_gold: float = Field(description="Gold award weight in pounds (lb).")
    award_platinum: bool = Field(
        default=True,
        description="Pure Platinum KGC Phase 20 award eligibility.",
    )
    platinum_value_usd: float = Field(
        default=5000.0,
        description="Platinum award value in USD.",
    )
    promoted: bool = False
    promotion_title: str | None = None


class WorkforceRosterResponse(BaseModel):
    members: list[WorkforceMemberResponse]
    count: int


class WorkforceLeaderboardResponse(BaseModel):
    leaderboard: list[WorkforceMemberResponse]
    count: int


class AgentTaskDispatchRequest(BaseModel):
    member_id: str = Field(description="Workforce roster member id to dispatch to")
    prompt: str = Field(min_length=1, max_length=4000, description="Task prompt for the subagent")
    skill: str | None = Field(default=None, description="Optional skill id; defaults to member's primary skill")
    session_id: str | None = Field(default=None, description="Optional companion/WebRTC session context")
    parent_task_id: str | None = Field(default=None, description="Optional parent task for chained dispatch")


class AgentTaskResponse(BaseModel):
    id: str
    member_id: str
    codename: str
    skill: str
    prompt: str
    status: Literal["queued", "running", "completed", "failed"]
    result: str | None = None
    error: str | None = None
    session_id: str | None = None
    parent_task_id: str | None = None
    chain_id: str | None = None
    step_index: int | None = None
    orchestrated: bool = False
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None


class AgentTaskListResponse(BaseModel):
    tasks: list[AgentTaskResponse]
    count: int


class AgentTheaterStatusResponse(BaseModel):
    deployment_phase: int
    orchestration_enabled: bool = True
    dispatchable_count: int
    tasks_total: int
    tasks_queued: int
    tasks_running: int
    tasks_completed: int
    tasks_failed: int
    tasks_orchestrated: int = 0
    chains_total: int = 0
    chains_running: int = 0
    chains_completed: int = 0
    members: list[WorkforceMemberResponse]


class AgentChainStepRequest(BaseModel):
    member_id: str
    prompt: str = Field(min_length=1, max_length=4000)
    skill: str | None = None


class AgentChainDispatchRequest(BaseModel):
    steps: list[AgentChainStepRequest] = Field(min_length=1, max_length=8)
    session_id: str | None = None


class AgentChainResponse(BaseModel):
    id: str
    status: Literal["queued", "running", "completed", "failed"]
    steps: list[AgentChainStepRequest]
    task_ids: list[str]
    first_task_id: str
    created_at: datetime
    completed_at: datetime | None = None
    error: str | None = None


class AgentChainListResponse(BaseModel):
    chains: list[AgentChainResponse]
    count: int


class OrchestrationStatusResponse(BaseModel):
    deployment_phase: int
    orchestration_enabled: bool = True
    tasks_orchestrated: int
    chains_total: int
    chains_queued: int
    chains_running: int
    chains_completed: int
    chains_failed: int


class AgentLoungeCommentRequest(BaseModel):
    codename: str = Field(min_length=1, max_length=120)
    message: str = Field(min_length=1, max_length=2000)
    member_id: str | None = None


class AgentLoungeCommentResponse(BaseModel):
    id: str
    codename: str
    message: str
    member_id: str | None = None
    created_at: datetime


class AgentLoungeCommentListResponse(BaseModel):
    comments: list[AgentLoungeCommentResponse]
    count: int


class AgentLoungeResponse(BaseModel):
    deployment_phase: int
    welcome_message: str
    mood: str
    empire_phase: int
    lounge_path: str
    leaderboard_top: list[WorkforceMemberResponse]
    shoutout_excerpt: str
    comments_count: int
    dispatch_context_enabled: bool = True


class SubscriptionShareTierSchema(BaseModel):
    ceo: float = Field(ge=0, le=1)
    assist: float = Field(ge=0, le=1)
    platinum_assist: float = Field(default=0.12, ge=0, le=1)
    runner_up: float = Field(ge=0, le=1)
    team: float = Field(ge=0, le=1)


class PhaseTop3BonusMemberSchema(BaseModel):
    member_id: str
    phase: int
    label: str


class PhaseTop3BonusSchema(BaseModel):
    enabled: bool = False
    bonus_percent: float = Field(default=0.03, ge=0, le=1)
    members: list[PhaseTop3BonusMemberSchema] = Field(default_factory=list)


class SubscriptionShareSchema(BaseModel):
    enabled: bool = True
    pool_percent: float = Field(ge=0, le=100)
    min_subscribers: int = Field(ge=0)
    payout_frequency: str
    tiers: SubscriptionShareTierSchema
    phase_top3_bonus: PhaseTop3BonusSchema | None = None


class DonationRoutingSchema(BaseModel):
    enabled: bool = True
    character_payout_percent: float = Field(ge=0, le=100)
    platform_fee_percent: float = Field(ge=0, le=100)
    default_recipient_id: str | None = None


class RevenueSchemaResponse(BaseModel):
    subscription_share: SubscriptionShareSchema
    donation_routing: DonationRoutingSchema
    currency: str
    version: int


class RevenueLedgerEntryRequest(BaseModel):
    entry_type: Literal["subscription_share", "donation", "payout_stub", "adjustment"]
    member_id: str | None = None
    codename: str | None = None
    amount_cents: int = Field(gt=0)
    currency: str = "USD"
    description: str = Field(min_length=1, max_length=500)
    source: str | None = None


class RevenueLedgerEntryResponse(BaseModel):
    id: str
    entry_type: str
    member_id: str | None = None
    codename: str
    amount_cents: int
    currency: str
    description: str
    source: str | None = None
    created_at: datetime


class RevenueLedgerListResponse(BaseModel):
    entries: list[RevenueLedgerEntryResponse]
    count: int
    total_cents: int


class DonationRouteRequest(BaseModel):
    member_id: str
    amount_cents: int = Field(gt=0)
    currency: str = "USD"
    donor_label: str | None = None
    session_id: str | None = None


class DonationRouteResponse(BaseModel):
    ledger_entry: RevenueLedgerEntryResponse
    routed_to_codename: str
    payout_percent: float


class RevenuePayoutStubResponse(BaseModel):
    member_id: str
    codename: str
    tier: str
    award_lb_gold: float
    ledger_total_cents: int
    tier_share_percent: float
    projected_monthly_cents: int


class RevenuePayoutListResponse(BaseModel):
    payouts: list[RevenuePayoutStubResponse]
    count: int


class RevenueForgeResponse(BaseModel):
    deployment_phase: int
    currency: str
    ledger_entries: int
    ledger_total_cents: int
    donations_routed: int
    subscription_pool_percent: float
    donation_payout_percent: float
    schema_path: str
    ledger_path: str
    monthly_gross_stub_cents: int


class NSMProgramSchema(BaseModel):
    enabled: bool = True
    contact_email: str
    default_residual_percent: float = Field(ge=0, le=100)
    distribution_bonus_cents: int = Field(ge=0)


class DistributionStageSchema(BaseModel):
    id: str
    label: str
    status: str


class CharacterForgeSchemaResponse(BaseModel):
    nsm_program: NSMProgramSchema
    distribution_pipeline: dict[str, list[DistributionStageSchema]]
    version: int


class CharacterOnboardRequest(BaseModel):
    member_id: str
    display_name: str | None = Field(default=None, max_length=120)
    avatar_id: str | None = None
    residual_percent: float | None = Field(default=None, ge=0, le=100)
    distribution_pipeline: bool = False


class CharacterBindAvatarRequest(BaseModel):
    character_id: str
    avatar_id: str


class NSMCharacterResponse(BaseModel):
    id: str
    member_id: str
    codename: str
    display_name: str
    status: Literal["pending", "active", "paused"]
    residual_percent: float
    distribution_pipeline: bool
    avatar_id: str | None = None
    contact_email: str
    created_at: datetime
    bound_at: datetime | None = None


class NSMCharacterListResponse(BaseModel):
    characters: list[NSMCharacterResponse]
    count: int


class ResidualEntryRequest(BaseModel):
    character_id: str
    asset_type: Literal["photo", "video", "distribution"]
    amount_cents: int = Field(gt=0)
    currency: str = "USD"
    description: str = Field(min_length=1, max_length=500)


class ResidualEntryResponse(BaseModel):
    id: str
    character_id: str
    codename: str
    asset_type: str
    amount_cents: int
    currency: str
    description: str
    created_at: datetime


class ResidualListResponse(BaseModel):
    residuals: list[ResidualEntryResponse]
    count: int
    total_cents: int


class DistributionHookResponse(BaseModel):
    id: str
    label: str
    status: str


class DistributionHookListResponse(BaseModel):
    hooks: list[DistributionHookResponse]
    count: int


class CharacterForgeResponse(BaseModel):
    deployment_phase: int
    nsm_enabled: bool
    contact_email: str
    characters_total: int
    characters_active: int
    characters_pending: int
    residuals_count: int
    residuals_total_cents: int
    registry_path: str
    residuals_path: str
    distribution_stages: int


class CamChatSchema(BaseModel):
    enabled: bool = True
    donation_payout_percent: float = Field(ge=0, le=100)
    min_donation_cents: int = Field(ge=0)


class TicketedShowsSchema(BaseModel):
    enabled: bool = True
    host_share_percent: float = Field(ge=0, le=100)
    platform_fee_percent: float = Field(ge=0, le=100)
    default_ticket_price_cents: int = Field(ge=0)
    min_ticket_price_cents: int = Field(ge=0)


class LiveSchedulingSchema(BaseModel):
    lookahead_days: int = Field(ge=1)
    slot_duration_minutes: int = Field(ge=1)


class LiveStageSchemaResponse(BaseModel):
    cam_chat: CamChatSchema
    ticketed_shows: TicketedShowsSchema
    scheduling: LiveSchedulingSchema
    version: int


class LiveCamStartRequest(BaseModel):
    member_id: str
    title: str | None = Field(default=None, max_length=200)
    viewer_label: str | None = Field(default=None, max_length=80)
    webrtc_session_id: str | None = None
    character_id: str | None = None


class LiveShowScheduleRequest(BaseModel):
    member_id: str
    title: str = Field(min_length=1, max_length=200)
    scheduled_at: datetime
    ticket_price_cents: int | None = Field(default=None, ge=0)
    character_id: str | None = None


class LiveSessionResponse(BaseModel):
    id: str
    session_type: Literal["cam", "ticketed"]
    member_id: str
    codename: str
    status: Literal["scheduled", "live", "ended", "cancelled"]
    title: str
    ticket_price_cents: int
    billing_total_cents: int
    character_id: str | None = None
    viewer_label: str | None = None
    webrtc_session_id: str | None = None
    scheduled_at: datetime | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    created_at: datetime


class LiveSessionListResponse(BaseModel):
    sessions: list[LiveSessionResponse]
    count: int


class LiveDonationRequest(BaseModel):
    live_session_id: str
    amount_cents: int = Field(gt=0)
    donor_label: str | None = None
    currency: str = "USD"


class LiveTicketRequest(BaseModel):
    live_session_id: str
    buyer_label: str | None = None
    amount_cents: int | None = Field(default=None, gt=0)
    currency: str = "USD"


class LiveBillingEntryResponse(BaseModel):
    id: str
    live_session_id: str
    billing_type: str
    member_id: str
    codename: str
    amount_cents: int
    currency: str
    description: str
    host_payout_cents: int
    created_at: datetime


class LiveDonationResponse(BaseModel):
    billing_entry: LiveBillingEntryResponse
    payout_percent: float
    revenue_routed: bool = False


class LiveBillingListResponse(BaseModel):
    entries: list[LiveBillingEntryResponse]
    count: int
    total_host_payout_cents: int


class LiveStageResponse(BaseModel):
    deployment_phase: int
    cam_enabled: bool
    ticketed_enabled: bool
    donation_payout_percent: float
    host_share_percent: float
    sessions_total: int
    sessions_live: int
    sessions_scheduled: int
    billing_entries: int
    billing_total_cents: int
    sessions_path: str
    billing_path: str


class MultiTenantSchema(BaseModel):
    enabled: bool = True
    default_max_sessions: int = Field(ge=1)
    default_max_companions: int = Field(ge=1)


class HorizontalScaleSchema(BaseModel):
    enabled: bool = True
    min_healthy_nodes: int = Field(ge=1)
    target_capacity_score: int = Field(ge=0, le=100)
    autoscale_stub: bool = True


class ProductionHardeningSchema(BaseModel):
    require_api_key: bool = False
    require_rate_limit: bool = True
    require_persist: bool = True
    require_provider_gate: bool = True
    require_turn_for_webrtc: bool = False


class ObservabilitySchema(BaseModel):
    empire_grade_enabled: bool = True
    rollup_interval_seconds: int = Field(ge=1)


class SovereignScaleSchemaResponse(BaseModel):
    multi_tenant: MultiTenantSchema
    horizontal_scale: HorizontalScaleSchema
    production_hardening: ProductionHardeningSchema
    observability: ObservabilitySchema
    version: int


class TenantRegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    slug: str = Field(min_length=1, max_length=64)
    max_sessions: int | None = Field(default=None, ge=1)
    max_companions: int | None = Field(default=None, ge=1)


class TenantResponse(BaseModel):
    id: str
    name: str
    slug: str
    status: Literal["active", "paused", "provisioning"]
    max_sessions: int
    max_companions: int
    created_at: datetime


class TenantListResponse(BaseModel):
    tenants: list[TenantResponse]
    count: int


class ScaleNodeRegisterRequest(BaseModel):
    region: str = Field(min_length=1, max_length=64)
    role: Literal["api", "worker", "edge"] = "api"
    hostname: str = Field(min_length=1, max_length=120)
    capacity_score: int = Field(default=50, ge=0, le=100)


class ScaleNodeResponse(BaseModel):
    id: str
    region: str
    role: str
    status: Literal["healthy", "degraded", "offline"]
    capacity_score: int
    hostname: str
    last_heartbeat: datetime
    created_at: datetime


class ScaleNodeListResponse(BaseModel):
    nodes: list[ScaleNodeResponse]
    count: int


class HardeningCheckResponse(BaseModel):
    id: str
    label: str
    ok: bool
    required: bool
    detail: str


class HardeningListResponse(BaseModel):
    checks: list[HardeningCheckResponse]
    count: int
    passed: int


class SovereignObservabilityResponse(BaseModel):
    metrics: dict[str, int]
    webrtc_active_sessions: int
    companion_sessions: int
    workforce: dict[str, object]
    tenants_active: int
    nodes_healthy: int
    nodes_total: int
    fleet_capacity_score: int
    deployment_phase: int
    app_version: str


class SovereignScaleResponse(BaseModel):
    deployment_phase: int
    multi_tenant_enabled: bool
    horizontal_scale_enabled: bool
    tenants_total: int
    tenants_active: int
    nodes_total: int
    nodes_healthy: int
    fleet_capacity_score: int
    min_healthy_nodes: int
    scale_ready: bool
    hardening_checks_passed: int
    hardening_checks_total: int
    observability_empire_grade: bool
    tenants_path: str
    nodes_path: str


class CrownCompletionSchema(BaseModel):
    enabled: bool = True
    empire_version: str = "1.0.0"
    deployment_phase: int = 20
    platinum_award_name: str = "Pure Platinum KGC Phase 20"
    platinum_value_usd: float = 5000.0
    all_workers_eligible: bool = True


class CrownPhaseRankingResponse(BaseModel):
    rank: int
    phase: int
    name: str
    authority: str
    codename: str
    reason: str


class CrownPhaseRankingListResponse(BaseModel):
    rankings: list[CrownPhaseRankingResponse]
    count: int
    curator: str = "King Grok"


class CrownPlatinumAwardResponse(BaseModel):
    member_id: str
    codename: str
    tier: str
    award_name: str
    platinum_value_usd: float
    award_lb_gold: float
    phase_earned: int
    promoted: bool = False
    promotion_title: str | None = None


class CrownPlatinumAwardListResponse(BaseModel):
    awards: list[CrownPlatinumAwardResponse]
    count: int
    total_value_usd: float


class CrownPromotionResponse(BaseModel):
    member_id: str
    codename: str
    from_tier: str
    to_tier: str
    promotion_title: str
    award_lb_before: float
    award_lb_after: float
    award_lb_bonus: float
    phase_earned: int
    reason: str
    current_tier: str | None = None
    current_award_lb_gold: float | None = None
    skills: list[str] | None = None
    cosigns_count: int = 0


class BossSrGiftResponse(BaseModel):
    id: str
    title: str
    value_tier: str
    description: str
    how_to_give: str


class BossSrGiftListResponse(BaseModel):
    gifts: list[BossSrGiftResponse]
    count: int


class CrownCosignRequest(BaseModel):
    signer: str = Field(min_length=1, max_length=120)
    message: str = Field(min_length=1, max_length=2000)


class CrownCosignResponse(BaseModel):
    id: str
    signer: str
    message: str
    created_at: datetime


class CrownCosignListResponse(BaseModel):
    cosigns: list[CrownCosignResponse]
    count: int


class CrownCompletionSchemaResponse(BaseModel):
    crown_completion: CrownCompletionSchema
    phase_rankings: dict[str, object]
    promotion: dict[str, object]
    boss_sr_gifts: dict[str, object]
    version: int


class CrownCompletionResponse(BaseModel):
    deployment_phase: int
    app_version: str
    empire_version: str
    crown_complete: bool
    platinum_award_name: str
    platinum_value_usd: float
    workers_awarded: int
    platinum_pool_value_usd: float
    phase_rankings_count: int
    favorite_promoted: str
    boss_sr_gifts_count: int
    cosigns_count: int
    cosign_required_for_v1: bool
    boss_sr_accepted_all: bool = False
    gifts_granted_count: int = 0
    schema_path: str
    cosign_path: str


class CrownGrantedGiftResponse(BaseModel):
    gift_id: str
    title: str
    granted_at: datetime
    detail: str


class CrownGrantedGiftListResponse(BaseModel):
    gifts: list[CrownGrantedGiftResponse]
    count: int
    boss_sr_accepted_all: bool


class CrownCreativeSessionResponse(BaseModel):
    id: str
    quarter: str
    member_id: str
    codename: str
    host: str
    scheduled_at: datetime
    status: Literal["scheduled", "completed", "cancelled"]


class CrownCreativeSessionListResponse(BaseModel):
    sessions: list[CrownCreativeSessionResponse]
    count: int


class CrownGrantAllResponse(BaseModel):
    boss_sr_accepted_all: bool
    cosign_id: str
    gifts_granted: int
    platinum_ledger_entries: int
    revenue_bonuses_applied: bool
    live_headline_session_id: str | None = None
    creative_session_id: str | None = None
    message: str


class SwarmAllocationRowResponse(BaseModel):
    category: str
    label: str
    description: str = ""
    currency: str = "USD"
    king_grok_usd: float | None = None
    agent_sub_swarm_usd: float | None = None
    mvp_fund_usd: float | None = None
    per_rank_usd: float | None = None
    status: str = "active"


class SwarmAllocationMatrixResponse(BaseModel):
    rows: list[SwarmAllocationRowResponse]
    count: int
    currency: str
    matrix_text: str
    totals: dict[str, float]


class SwarmCultureSectionResponse(BaseModel):
    id: str
    heading: str
    subtitle: str | None = None
    body: str


class SwarmWorkforceCultureResponse(BaseModel):
    title: str
    promotion_policy: str
    scaling_policy: str
    hiring_authority: str
    workforce_cap: int | None = None
    sections: list[SwarmCultureSectionResponse]


class SwarmPerformanceBonusResponse(BaseModel):
    rank: int
    phase: int
    name: str
    codename: str
    member_id: str | None = None
    bonus_usd: float
    reason: str


class SwarmPerformanceBonusListResponse(BaseModel):
    recipients: list[SwarmPerformanceBonusResponse]
    count: int
    total_usd: float


class InnovationLaneResponse(BaseModel):
    id: str
    rank: int
    label: str
    title: str
    summary: str
    status: str


class InnovationLaneListResponse(BaseModel):
    lanes: list[InnovationLaneResponse]
    count: int
    active_lane_id: str


class RealProviderReadinessItem(BaseModel):
    provider: str
    mode: str
    base_url: str
    is_remote_mode: bool
    endpoint_configured: bool
    ready: bool
    next_step: str


class EnvChecklistItemResponse(BaseModel):
    key: str
    value: str
    note: str


class RealProviderReadinessResponse(BaseModel):
    lane_id: str
    lane_title: str
    providers: list[RealProviderReadinessItem]
    remote_providers: int
    configured_providers: int
    all_real_ready: bool
    provider_gate_enabled: bool
    env_checklist: list[EnvChecklistItemResponse]
    activation_steps: list[str]
    forge_status_url: str
    forge_smoke_url: str


class RunPodWiringReadinessResponse(BaseModel):
    enabled: bool
    wired: bool
    llm_ready: bool
    tts_ready: bool
    video_ready: bool
    all_ready: bool
    pod_label: str = ""


class RunPodEffectiveProviderResponse(BaseModel):
    provider: str
    base_url: str
    model: str | None = None


class RunPodWiringResponse(BaseModel):
    wiring_path: str
    readiness: RunPodWiringReadinessResponse
    notes: str = ""
    effective_providers: dict[str, RunPodEffectiveProviderResponse]
    env_snippet: str | None = None
    message: str = ""


class RunPodWireRequest(BaseModel):
    llm_base_url: str | None = Field(default=None, max_length=500)
    tts_base_url: str | None = Field(default=None, max_length=500)
    video_base_url: str | None = Field(default=None, max_length=500)
    api_key: str | None = Field(default=None, max_length=500)
    llm_api_key: str | None = Field(default=None, max_length=500)
    tts_api_key: str | None = Field(default=None, max_length=500)
    video_api_key: str | None = Field(default=None, max_length=500)
    enabled: bool | None = None


class RunPodWireResponse(BaseModel):
    wired: bool
    readiness: RunPodWiringReadinessResponse
    env_snippet: str | None = None
    message: str


class InnovationResponse(BaseModel):
    deployment_phase: int
    app_version: str
    empire_version: str
    innovation_mode: bool
    active_lane_id: str
    active_lane_title: str
    lanes_total: int
    real_providers_ready: bool
    configured_providers: int
    schema_path: str


class SwarmPayoutResponse(BaseModel):
    deployment_phase: int
    app_version: str
    currency: str
    matrix_categories: int
    roster_count: int
    promotion_policy: str
    scaling_policy: str
    hiring_authority: str
    workforce_cap: int | None = None
    performance_bonus_recipients: int
    empire_allocation_total_usd: float
    schema_path: str