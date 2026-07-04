from fastapi import APIRouter, HTTPException, Query, Request, status

from app.models.workforce import (
    AgentChainDispatchRequest,
    AgentChainListResponse,
    AgentChainResponse,
    AgentChainStepRequest,
    AgentLoungeCommentListResponse,
    AgentLoungeCommentRequest,
    AgentLoungeCommentResponse,
    AgentLoungeResponse,
    AgentTaskDispatchRequest,
    AgentTaskListResponse,
    AgentTaskResponse,
    AgentTheaterStatusResponse,
    BossSrGiftListResponse,
    BossSrGiftResponse,
    CharacterBindAvatarRequest,
    CharacterForgeResponse,
    CrownCompletionResponse,
    CrownCompletionSchema,
    CrownCompletionSchemaResponse,
    CrownCosignListResponse,
    CrownCosignRequest,
    CrownCosignResponse,
    CrownCreativeSessionListResponse,
    CrownCreativeSessionResponse,
    CrownGrantAllResponse,
    CrownGrantedGiftListResponse,
    CrownGrantedGiftResponse,
    CrownPhaseRankingListResponse,
    CrownPhaseRankingResponse,
    CrownPlatinumAwardListResponse,
    CrownPlatinumAwardResponse,
    CrownPromotionResponse,
    CharacterForgeSchemaResponse,
    CamChatSchema,
    CharacterOnboardRequest,
    DistributionHookListResponse,
    DistributionHookResponse,
    DistributionStageSchema,
    DonationRouteRequest,
    DonationRouteResponse,
    DonationRoutingSchema,
    NSMCharacterListResponse,
    NSMCharacterResponse,
    LiveBillingEntryResponse,
    LiveBillingListResponse,
    LiveCamStartRequest,
    LiveDonationRequest,
    LiveDonationResponse,
    LiveSchedulingSchema,
    LiveSessionListResponse,
    LiveSessionResponse,
    LiveShowScheduleRequest,
    LiveStageResponse,
    LiveStageSchemaResponse,
    LiveTicketRequest,
    NSMProgramSchema,
    OrchestrationStatusResponse,
    TicketedShowsSchema,
    ResidualEntryRequest,
    ResidualEntryResponse,
    HardeningCheckResponse,
    HardeningListResponse,
    HorizontalScaleSchema,
    MultiTenantSchema,
    ObservabilitySchema,
    ProductionHardeningSchema,
    ResidualListResponse,
    RevenueForgeResponse,
    ScaleNodeListResponse,
    ScaleNodeRegisterRequest,
    ScaleNodeResponse,
    SovereignObservabilityResponse,
    SovereignScaleResponse,
    SovereignScaleSchemaResponse,
    SwarmAllocationMatrixResponse,
    SwarmAllocationRowResponse,
    SwarmPayoutResponse,
    SwarmPerformanceBonusListResponse,
    SwarmPerformanceBonusResponse,
    SwarmWorkforceCultureResponse,
    SwarmCultureSectionResponse,
    TenantListResponse,
    TenantRegisterRequest,
    TenantResponse,
    RevenueLedgerEntryRequest,
    RevenueLedgerEntryResponse,
    RevenueLedgerListResponse,
    RevenuePayoutListResponse,
    RevenuePayoutStubResponse,
    RevenueSchemaResponse,
    SubscriptionShareSchema,
    WorkforceLeaderboardResponse,
    WorkforceMemberResponse,
    WorkforceRosterResponse,
)
from app.services.workforce.context_builder import build_workforce_context
from app.services.workforce.orchestration import ChainStepRequest
from app.services.workforce.theater import AgentTaskRecord
from app.workforce.roster import get_leaderboard, get_roster

router = APIRouter(prefix="/workforce", tags=["workforce"])


def _task_response(record: AgentTaskRecord) -> AgentTaskResponse:
    return AgentTaskResponse(
        id=record.id,
        member_id=record.member_id,
        codename=record.codename,
        skill=record.skill,
        prompt=record.prompt,
        status=record.status,
        result=record.result,
        error=record.error,
        session_id=record.session_id,
        parent_task_id=record.parent_task_id,
        chain_id=record.chain_id,
        step_index=record.step_index,
        orchestrated=record.orchestrated,
        created_at=record.created_at,
        started_at=record.started_at,
        completed_at=record.completed_at,
        duration_ms=record.duration_ms,
    )


def _character_response(character) -> NSMCharacterResponse:
    return NSMCharacterResponse(
        id=character.id,
        member_id=character.member_id,
        codename=character.codename,
        display_name=character.display_name,
        status=character.status,
        residual_percent=character.residual_percent,
        distribution_pipeline=character.distribution_pipeline,
        avatar_id=character.avatar_id,
        contact_email=character.contact_email,
        created_at=character.created_at,
        bound_at=character.bound_at,
    )


def _tenant_response(tenant) -> TenantResponse:
    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        status=tenant.status,
        max_sessions=tenant.max_sessions,
        max_companions=tenant.max_companions,
        created_at=tenant.created_at,
    )


def _scale_node_response(node) -> ScaleNodeResponse:
    return ScaleNodeResponse(
        id=node.id,
        region=node.region,
        role=node.role,
        status=node.status,
        capacity_score=node.capacity_score,
        hostname=node.hostname,
        last_heartbeat=node.last_heartbeat,
        created_at=node.created_at,
    )


def _live_session_response(session) -> LiveSessionResponse:
    return LiveSessionResponse(
        id=session.id,
        session_type=session.session_type,
        member_id=session.member_id,
        codename=session.codename,
        status=session.status,
        title=session.title,
        ticket_price_cents=session.ticket_price_cents,
        billing_total_cents=session.billing_total_cents,
        character_id=session.character_id,
        viewer_label=session.viewer_label,
        webrtc_session_id=session.webrtc_session_id,
        scheduled_at=session.scheduled_at,
        started_at=session.started_at,
        ended_at=session.ended_at,
        created_at=session.created_at,
    )


def _live_billing_response(entry) -> LiveBillingEntryResponse:
    return LiveBillingEntryResponse(
        id=entry.id,
        live_session_id=entry.live_session_id,
        billing_type=entry.billing_type,
        member_id=entry.member_id,
        codename=entry.codename,
        amount_cents=entry.amount_cents,
        currency=entry.currency,
        description=entry.description,
        host_payout_cents=entry.host_payout_cents,
        created_at=entry.created_at,
    )


def _residual_response(entry) -> ResidualEntryResponse:
    return ResidualEntryResponse(
        id=entry.id,
        character_id=entry.character_id,
        codename=entry.codename,
        asset_type=entry.asset_type,
        amount_cents=entry.amount_cents,
        currency=entry.currency,
        description=entry.description,
        created_at=entry.created_at,
    )


def _ledger_entry_response(entry) -> RevenueLedgerEntryResponse:
    return RevenueLedgerEntryResponse(
        id=entry.id,
        entry_type=entry.entry_type,
        member_id=entry.member_id,
        codename=entry.codename,
        amount_cents=entry.amount_cents,
        currency=entry.currency,
        description=entry.description,
        source=entry.source,
        created_at=entry.created_at,
    )


def _chain_response(chain_id: str, theater) -> AgentChainResponse:
    chain = theater.orchestration.get_chain(chain_id)
    if chain is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown chain {chain_id!r}")
    steps = [AgentChainStepRequest(**step) for step in chain.steps]
    first_task_id = chain.task_ids[0] if chain.task_ids else ""
    return AgentChainResponse(
        id=chain.id,
        status=chain.status,
        steps=steps,
        task_ids=list(chain.task_ids),
        first_task_id=first_task_id,
        created_at=chain.created_at,
        completed_at=chain.completed_at,
        error=chain.error,
    )


@router.get(
    "/roster",
    response_model=WorkforceRosterResponse,
    summary="Full named agent workforce roster",
)
async def workforce_roster() -> WorkforceRosterResponse:
    members = [WorkforceMemberResponse(**member) for member in get_roster()]
    return WorkforceRosterResponse(members=members, count=len(members))


@router.get(
    "/leaderboard",
    response_model=WorkforceLeaderboardResponse,
    summary="Workforce sorted by gold award (highest first)",
)
async def workforce_leaderboard() -> WorkforceLeaderboardResponse:
    leaderboard = [WorkforceMemberResponse(**member) for member in get_leaderboard()]
    return WorkforceLeaderboardResponse(leaderboard=leaderboard, count=len(leaderboard))


@router.get(
    "/theater",
    response_model=AgentTheaterStatusResponse,
    summary="Agent Theater status and dispatchable roster",
)
async def agent_theater_status(request: Request) -> AgentTheaterStatusResponse:
    theater = request.app.state.agent_theater
    ctx = build_workforce_context(request)
    await theater.progress_tasks(ctx)
    settings = request.app.state.settings
    status_data = theater.status()
    members = [WorkforceMemberResponse(**member) for member in get_roster()]
    return AgentTheaterStatusResponse(
        deployment_phase=settings.deployment_phase,
        orchestration_enabled=True,
        members=members,
        **status_data,
    )


@router.get(
    "/theater/tasks",
    response_model=AgentTaskListResponse,
    summary="List recent Agent Theater dispatched tasks",
)
async def agent_theater_tasks(
    request: Request,
    limit: int = Query(default=50, ge=1, le=100),
) -> AgentTaskListResponse:
    theater = request.app.state.agent_theater
    ctx = build_workforce_context(request)
    await theater.progress_tasks(ctx)
    tasks = [_task_response(record) for record in theater.list_tasks(limit=limit)]
    return AgentTaskListResponse(tasks=tasks, count=len(tasks))


@router.get(
    "/theater/tasks/{task_id}",
    response_model=AgentTaskResponse,
    summary="Get a single Agent Theater task by id",
)
async def agent_theater_task(request: Request, task_id: str) -> AgentTaskResponse:
    theater = request.app.state.agent_theater
    ctx = build_workforce_context(request)
    await theater.progress_tasks(ctx)
    record = theater.get_task(task_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown task {task_id!r}")
    return _task_response(record)


@router.post(
    "/theater/dispatch",
    response_model=AgentTaskResponse,
    summary="Dispatch a task to a workforce subagent",
)
async def agent_theater_dispatch(
    request: Request,
    body: AgentTaskDispatchRequest,
) -> AgentTaskResponse:
    theater = request.app.state.agent_theater
    record = await theater.dispatch(
        member_id=body.member_id,
        prompt=body.prompt,
        skill=body.skill,
        session_id=body.session_id,
        parent_task_id=body.parent_task_id,
    )
    ctx = build_workforce_context(request)
    await theater.progress_tasks(ctx)
    return _task_response(record)


@router.get(
    "/orchestration",
    response_model=OrchestrationStatusResponse,
    summary="Orchestration Forge status (Phase 14)",
)
async def orchestration_status(request: Request) -> OrchestrationStatusResponse:
    theater = request.app.state.agent_theater
    ctx = build_workforce_context(request)
    await theater.progress_tasks(ctx)
    settings = request.app.state.settings
    status_data = theater.status()
    return OrchestrationStatusResponse(
        deployment_phase=settings.deployment_phase,
        orchestration_enabled=True,
        tasks_orchestrated=status_data.get("tasks_orchestrated", 0),
        chains_total=status_data.get("chains_total", 0),
        chains_queued=status_data.get("chains_queued", 0),
        chains_running=status_data.get("chains_running", 0),
        chains_completed=status_data.get("chains_completed", 0),
        chains_failed=status_data.get("chains_failed", 0),
    )


@router.post(
    "/orchestration/chain",
    response_model=AgentChainResponse,
    summary="Dispatch a multi-step task chain across subagents",
)
async def orchestration_chain_dispatch(
    request: Request,
    body: AgentChainDispatchRequest,
) -> AgentChainResponse:
    theater = request.app.state.agent_theater
    steps = [ChainStepRequest(**step.model_dump()) for step in body.steps]
    chain_id, _record = await theater.dispatch_chain(steps=steps, session_id=body.session_id)
    ctx = build_workforce_context(request)
    await theater.progress_tasks(ctx)
    return _chain_response(chain_id, theater)


@router.get(
    "/orchestration/chains",
    response_model=AgentChainListResponse,
    summary="List recent orchestration chains",
)
async def orchestration_chain_list(
    request: Request,
    limit: int = Query(default=20, ge=1, le=50),
) -> AgentChainListResponse:
    theater = request.app.state.agent_theater
    ctx = build_workforce_context(request)
    await theater.progress_tasks(ctx)
    chains = [
        _chain_response(chain.id, theater)
        for chain in theater.orchestration.list_chains(limit=limit)
    ]
    return AgentChainListResponse(chains=chains, count=len(chains))


@router.get(
    "/orchestration/chains/{chain_id}",
    response_model=AgentChainResponse,
    summary="Get a single orchestration chain by id",
)
async def orchestration_chain_detail(request: Request, chain_id: str) -> AgentChainResponse:
    theater = request.app.state.agent_theater
    ctx = build_workforce_context(request)
    await theater.progress_tasks(ctx)
    return _chain_response(chain_id, theater)


@router.get(
    "/lounge",
    response_model=AgentLoungeResponse,
    summary="Agent Lounge — morale, rankings, shoutouts (Phase 15)",
)
async def agent_lounge_status(request: Request) -> AgentLoungeResponse:
    lounge = request.app.state.agent_lounge
    settings = request.app.state.settings
    snap = lounge.snapshot(deployment_phase=settings.deployment_phase)
    return AgentLoungeResponse(
        deployment_phase=snap["deployment_phase"],  # type: ignore[arg-type]
        welcome_message=snap["welcome_message"],  # type: ignore[arg-type]
        mood=snap["mood"],  # type: ignore[arg-type]
        empire_phase=snap["empire_phase"],  # type: ignore[arg-type]
        lounge_path=snap["lounge_path"],  # type: ignore[arg-type]
        leaderboard_top=[
            WorkforceMemberResponse(**member) for member in snap["leaderboard_top"]  # type: ignore[union-attr]
        ],
        shoutout_excerpt=snap["shoutout_excerpt"],  # type: ignore[arg-type]
        comments_count=snap["comments_count"],  # type: ignore[arg-type]
        dispatch_context_enabled=snap["dispatch_context_enabled"],  # type: ignore[arg-type]
    )


@router.get(
    "/lounge/comments",
    response_model=AgentLoungeCommentListResponse,
    summary="Agent Lounge comment board",
)
async def agent_lounge_comments(
    request: Request,
    limit: int = Query(default=50, ge=1, le=100),
) -> AgentLoungeCommentListResponse:
    lounge = request.app.state.agent_lounge
    comments = [
        AgentLoungeCommentResponse(
            id=comment.id,
            codename=comment.codename,
            message=comment.message,
            member_id=comment.member_id,
            created_at=comment.created_at,
        )
        for comment in lounge.list_comments(limit=limit)
    ]
    return AgentLoungeCommentListResponse(comments=comments, count=len(comments))


@router.post(
    "/lounge/comments",
    response_model=AgentLoungeCommentResponse,
    summary="Post a comment to the Agent Lounge board",
)
async def agent_lounge_post_comment(
    request: Request,
    body: AgentLoungeCommentRequest,
) -> AgentLoungeCommentResponse:
    lounge = request.app.state.agent_lounge
    comment = lounge.add_comment(
        codename=body.codename,
        message=body.message,
        member_id=body.member_id,
    )
    return AgentLoungeCommentResponse(
        id=comment.id,
        codename=comment.codename,
        message=comment.message,
        member_id=comment.member_id,
        created_at=comment.created_at,
    )


@router.get(
    "/revenue",
    response_model=RevenueForgeResponse,
    summary="Revenue Forge status — ledger totals and share schema (Phase 16)",
)
async def revenue_forge_status(request: Request) -> RevenueForgeResponse:
    revenue = request.app.state.revenue_forge
    settings = request.app.state.settings
    snap = revenue.snapshot(deployment_phase=settings.deployment_phase)
    return RevenueForgeResponse(**snap)  # type: ignore[arg-type]


@router.get(
    "/revenue/schema",
    response_model=RevenueSchemaResponse,
    summary="Subscription share and donation routing schema",
)
async def revenue_forge_schema(request: Request) -> RevenueSchemaResponse:
    revenue = request.app.state.revenue_forge
    raw = revenue.get_schema()
    return RevenueSchemaResponse(
        subscription_share=SubscriptionShareSchema(**raw["subscription_share"]),
        donation_routing=DonationRoutingSchema(**raw["donation_routing"]),
        currency=str(raw.get("currency", "USD")),
        version=int(raw.get("version", 1)),
    )


@router.get(
    "/revenue/ledger",
    response_model=RevenueLedgerListResponse,
    summary="Earnings ledger entries (newest first)",
)
async def revenue_forge_ledger(
    request: Request,
    limit: int = Query(default=50, ge=1, le=100),
) -> RevenueLedgerListResponse:
    revenue = request.app.state.revenue_forge
    settings = request.app.state.settings
    entries = [_ledger_entry_response(entry) for entry in revenue.list_ledger(limit=limit)]
    snap = revenue.snapshot(deployment_phase=settings.deployment_phase)
    return RevenueLedgerListResponse(
        entries=entries,
        count=len(entries),
        total_cents=int(snap["ledger_total_cents"]),
    )


@router.post(
    "/revenue/ledger",
    response_model=RevenueLedgerEntryResponse,
    summary="Record an earnings ledger entry",
)
async def revenue_forge_record_entry(
    request: Request,
    body: RevenueLedgerEntryRequest,
) -> RevenueLedgerEntryResponse:
    revenue = request.app.state.revenue_forge
    entry = revenue.record_entry(
        entry_type=body.entry_type,
        member_id=body.member_id,
        codename=body.codename,
        amount_cents=body.amount_cents,
        currency=body.currency,
        description=body.description,
        source=body.source,
    )
    return _ledger_entry_response(entry)


@router.post(
    "/revenue/donations/route",
    response_model=DonationRouteResponse,
    summary="Route a cam donation to a roster member (100% character payout stub)",
)
async def revenue_forge_route_donation(
    request: Request,
    body: DonationRouteRequest,
) -> DonationRouteResponse:
    revenue = request.app.state.revenue_forge
    entry, payout_percent = revenue.route_donation(
        member_id=body.member_id,
        amount_cents=body.amount_cents,
        currency=body.currency,
        donor_label=body.donor_label,
        session_id=body.session_id,
    )
    return DonationRouteResponse(
        ledger_entry=_ledger_entry_response(entry),
        routed_to_codename=entry.codename,
        payout_percent=payout_percent,
    )


@router.get(
    "/revenue/payouts",
    response_model=RevenuePayoutListResponse,
    summary="Roster payout stubs from ledger + subscription share schema",
)
async def revenue_forge_payouts(request: Request) -> RevenuePayoutListResponse:
    revenue = request.app.state.revenue_forge
    payouts = [
        RevenuePayoutStubResponse(**stub) for stub in revenue.compute_payout_stubs()
    ]
    return RevenuePayoutListResponse(payouts=payouts, count=len(payouts))


@router.get(
    "/characters",
    response_model=CharacterForgeResponse,
    summary="Character Forge status — NSM registry and residuals (Phase 17)",
)
async def character_forge_status(request: Request) -> CharacterForgeResponse:
    forge = request.app.state.character_forge
    settings = request.app.state.settings
    snap = forge.snapshot(deployment_phase=settings.deployment_phase)
    return CharacterForgeResponse(**snap)  # type: ignore[arg-type]


@router.get(
    "/characters/schema",
    response_model=CharacterForgeSchemaResponse,
    summary="NSM program schema and distribution pipeline stages",
)
async def character_forge_schema(request: Request) -> CharacterForgeSchemaResponse:
    forge = request.app.state.character_forge
    raw = forge.get_schema()
    pipeline = raw.get("distribution_pipeline", {})
    stages_raw = pipeline.get("stages", []) if isinstance(pipeline, dict) else []
    stages = [DistributionStageSchema(**stage) for stage in stages_raw if isinstance(stage, dict)]
    return CharacterForgeSchemaResponse(
        nsm_program=NSMProgramSchema(**raw["nsm_program"]),
        distribution_pipeline={"stages": stages},
        version=int(raw.get("version", 1)),
    )


@router.get(
    "/characters/registry",
    response_model=NSMCharacterListResponse,
    summary="NSM character registry",
)
async def character_forge_registry(
    request: Request,
    limit: int = Query(default=50, ge=1, le=100),
) -> NSMCharacterListResponse:
    forge = request.app.state.character_forge
    characters = [_character_response(c) for c in forge.list_characters(limit=limit)]
    return NSMCharacterListResponse(characters=characters, count=len(characters))


@router.post(
    "/characters/onboard",
    response_model=NSMCharacterResponse,
    summary="Onboard a roster member as an NSM character",
)
async def character_forge_onboard(
    request: Request,
    body: CharacterOnboardRequest,
) -> NSMCharacterResponse:
    forge = request.app.state.character_forge
    character = forge.onboard(
        member_id=body.member_id,
        display_name=body.display_name,
        avatar_id=body.avatar_id,
        residual_percent=body.residual_percent,
        distribution_pipeline=body.distribution_pipeline,
    )
    return _character_response(character)


@router.post(
    "/characters/bind",
    response_model=NSMCharacterResponse,
    summary="Bind a companion avatar to an NSM character",
)
async def character_forge_bind(
    request: Request,
    body: CharacterBindAvatarRequest,
) -> NSMCharacterResponse:
    forge = request.app.state.character_forge
    character = forge.bind_avatar(character_id=body.character_id, avatar_id=body.avatar_id)
    return _character_response(character)


@router.get(
    "/characters/residuals",
    response_model=ResidualListResponse,
    summary="Residual tracking entries (photos, videos, distribution)",
)
async def character_forge_residuals(
    request: Request,
    limit: int = Query(default=50, ge=1, le=100),
) -> ResidualListResponse:
    forge = request.app.state.character_forge
    settings = request.app.state.settings
    residuals = [_residual_response(entry) for entry in forge.list_residuals(limit=limit)]
    snap = forge.snapshot(deployment_phase=settings.deployment_phase)
    return ResidualListResponse(
        residuals=residuals,
        count=len(residuals),
        total_cents=int(snap["residuals_total_cents"]),
    )


@router.post(
    "/characters/residuals",
    response_model=ResidualEntryResponse,
    summary="Record a residual ledger entry for an NSM character",
)
async def character_forge_record_residual(
    request: Request,
    body: ResidualEntryRequest,
) -> ResidualEntryResponse:
    forge = request.app.state.character_forge
    entry = forge.record_residual(
        character_id=body.character_id,
        asset_type=body.asset_type,
        amount_cents=body.amount_cents,
        description=body.description,
        currency=body.currency,
    )
    return _residual_response(entry)


@router.get(
    "/characters/distribution",
    response_model=DistributionHookListResponse,
    summary="Distribution pipeline hooks and stage status",
)
async def character_forge_distribution(request: Request) -> DistributionHookListResponse:
    forge = request.app.state.character_forge
    hooks = [
        DistributionHookResponse(**hook) for hook in forge.distribution_hooks()
    ]
    return DistributionHookListResponse(hooks=hooks, count=len(hooks))


@router.get(
    "/live",
    response_model=LiveStageResponse,
    summary="Live Stage status — cam chat and ticketed shows (Phase 18)",
)
async def live_stage_status(request: Request) -> LiveStageResponse:
    stage = request.app.state.live_stage
    settings = request.app.state.settings
    snap = stage.snapshot(deployment_phase=settings.deployment_phase)
    return LiveStageResponse(**snap)  # type: ignore[arg-type]


@router.get(
    "/live/schema",
    response_model=LiveStageSchemaResponse,
    summary="Cam chat and ticketed show billing schema",
)
async def live_stage_schema(request: Request) -> LiveStageSchemaResponse:
    stage = request.app.state.live_stage
    raw = stage.get_schema()
    return LiveStageSchemaResponse(
        cam_chat=CamChatSchema(**raw["cam_chat"]),
        ticketed_shows=TicketedShowsSchema(**raw["ticketed_shows"]),
        scheduling=LiveSchedulingSchema(**raw["scheduling"]),
        version=int(raw.get("version", 1)),
    )


@router.get(
    "/live/sessions",
    response_model=LiveSessionListResponse,
    summary="Live and scheduled stage sessions",
)
async def live_stage_sessions(
    request: Request,
    limit: int = Query(default=50, ge=1, le=100),
) -> LiveSessionListResponse:
    stage = request.app.state.live_stage
    sessions = [_live_session_response(s) for s in stage.list_sessions(limit=limit)]
    return LiveSessionListResponse(sessions=sessions, count=len(sessions))


@router.post(
    "/live/cam/start",
    response_model=LiveSessionResponse,
    summary="Start a cam chat live session",
)
async def live_stage_cam_start(
    request: Request,
    body: LiveCamStartRequest,
) -> LiveSessionResponse:
    stage = request.app.state.live_stage
    session = stage.start_cam(
        member_id=body.member_id,
        title=body.title,
        viewer_label=body.viewer_label,
        webrtc_session_id=body.webrtc_session_id,
        character_id=body.character_id,
    )
    return _live_session_response(session)


@router.post(
    "/live/sessions/{session_id}/end",
    response_model=LiveSessionResponse,
    summary="End a live or scheduled stage session",
)
async def live_stage_end_session(request: Request, session_id: str) -> LiveSessionResponse:
    stage = request.app.state.live_stage
    session = stage.end_session(session_id=session_id)
    return _live_session_response(session)


@router.post(
    "/live/shows/schedule",
    response_model=LiveSessionResponse,
    summary="Schedule a ticketed private show",
)
async def live_stage_schedule_show(
    request: Request,
    body: LiveShowScheduleRequest,
) -> LiveSessionResponse:
    stage = request.app.state.live_stage
    session = stage.schedule_show(
        member_id=body.member_id,
        title=body.title,
        scheduled_at=body.scheduled_at,
        ticket_price_cents=body.ticket_price_cents,
        character_id=body.character_id,
    )
    return _live_session_response(session)


@router.post(
    "/live/shows/{show_id}/start",
    response_model=LiveSessionResponse,
    summary="Start a scheduled ticketed show",
)
async def live_stage_start_show(request: Request, show_id: str) -> LiveSessionResponse:
    stage = request.app.state.live_stage
    session = stage.start_show(session_id=show_id)
    return _live_session_response(session)


@router.post(
    "/live/billing/donation",
    response_model=LiveDonationResponse,
    summary="Record a cam donation during a live session (routes to Revenue Forge)",
)
async def live_stage_cam_donation(
    request: Request,
    body: LiveDonationRequest,
) -> LiveDonationResponse:
    stage = request.app.state.live_stage
    revenue = request.app.state.revenue_forge
    billing_entry, payout_percent = stage.record_cam_donation(
        session_id=body.live_session_id,
        amount_cents=body.amount_cents,
        donor_label=body.donor_label,
        currency=body.currency,
    )
    revenue_routed = False
    try:
        revenue.route_donation(
            member_id=billing_entry.member_id,
            amount_cents=body.amount_cents,
            donor_label=body.donor_label,
            session_id=body.live_session_id,
            currency=body.currency,
        )
        revenue_routed = True
    except HTTPException:
        revenue_routed = False
    return LiveDonationResponse(
        billing_entry=_live_billing_response(billing_entry),
        payout_percent=payout_percent,
        revenue_routed=revenue_routed,
    )


@router.post(
    "/live/billing/ticket",
    response_model=LiveBillingEntryResponse,
    summary="Record a ticket sale for a scheduled/live show",
)
async def live_stage_ticket_sale(
    request: Request,
    body: LiveTicketRequest,
) -> LiveBillingEntryResponse:
    stage = request.app.state.live_stage
    entry = stage.record_ticket_sale(
        session_id=body.live_session_id,
        buyer_label=body.buyer_label,
        amount_cents=body.amount_cents,
        currency=body.currency,
    )
    return _live_billing_response(entry)


@router.get(
    "/live/billing",
    response_model=LiveBillingListResponse,
    summary="Live session billing ledger",
)
async def live_stage_billing(
    request: Request,
    limit: int = Query(default=50, ge=1, le=100),
) -> LiveBillingListResponse:
    stage = request.app.state.live_stage
    settings = request.app.state.settings
    entries = [_live_billing_response(e) for e in stage.list_billing(limit=limit)]
    snap = stage.snapshot(deployment_phase=settings.deployment_phase)
    return LiveBillingListResponse(
        entries=entries,
        count=len(entries),
        total_host_payout_cents=int(snap["billing_total_cents"]),
    )


@router.get(
    "/scale",
    response_model=SovereignScaleResponse,
    summary="Sovereign Scale status — tenants, nodes, hardening (Phase 19)",
)
async def sovereign_scale_status(request: Request) -> SovereignScaleResponse:
    scale = request.app.state.sovereign_scale
    settings = request.app.state.settings
    snap = scale.snapshot(deployment_phase=settings.deployment_phase, settings=settings)
    return SovereignScaleResponse(**snap)  # type: ignore[arg-type]


@router.get(
    "/scale/schema",
    response_model=SovereignScaleSchemaResponse,
    summary="Multi-tenant, horizontal scale, and hardening schema",
)
async def sovereign_scale_schema(request: Request) -> SovereignScaleSchemaResponse:
    scale = request.app.state.sovereign_scale
    raw = scale.get_schema()
    return SovereignScaleSchemaResponse(
        multi_tenant=MultiTenantSchema(**raw["multi_tenant"]),
        horizontal_scale=HorizontalScaleSchema(**raw["horizontal_scale"]),
        production_hardening=ProductionHardeningSchema(**raw["production_hardening"]),
        observability=ObservabilitySchema(**raw["observability"]),
        version=int(raw.get("version", 1)),
    )


@router.get(
    "/scale/tenants",
    response_model=TenantListResponse,
    summary="Multi-tenant fleet registry",
)
async def sovereign_scale_tenants(
    request: Request,
    limit: int = Query(default=50, ge=1, le=100),
) -> TenantListResponse:
    scale = request.app.state.sovereign_scale
    tenants = [_tenant_response(t) for t in scale.list_tenants(limit=limit)]
    return TenantListResponse(tenants=tenants, count=len(tenants))


@router.post(
    "/scale/tenants",
    response_model=TenantResponse,
    summary="Register a new tenant",
)
async def sovereign_scale_register_tenant(
    request: Request,
    body: TenantRegisterRequest,
) -> TenantResponse:
    scale = request.app.state.sovereign_scale
    tenant = scale.register_tenant(
        name=body.name,
        slug=body.slug,
        max_sessions=body.max_sessions,
        max_companions=body.max_companions,
    )
    return _tenant_response(tenant)


@router.get(
    "/scale/nodes",
    response_model=ScaleNodeListResponse,
    summary="Horizontal scale node fleet",
)
async def sovereign_scale_nodes(
    request: Request,
    limit: int = Query(default=50, ge=1, le=100),
) -> ScaleNodeListResponse:
    scale = request.app.state.sovereign_scale
    nodes = [_scale_node_response(n) for n in scale.list_nodes(limit=limit)]
    return ScaleNodeListResponse(nodes=nodes, count=len(nodes))


@router.post(
    "/scale/nodes",
    response_model=ScaleNodeResponse,
    summary="Register a scale node",
)
async def sovereign_scale_register_node(
    request: Request,
    body: ScaleNodeRegisterRequest,
) -> ScaleNodeResponse:
    scale = request.app.state.sovereign_scale
    node = scale.register_node(
        region=body.region,
        role=body.role,
        hostname=body.hostname,
        capacity_score=body.capacity_score,
    )
    return _scale_node_response(node)


@router.post(
    "/scale/nodes/{node_id}/heartbeat",
    response_model=ScaleNodeResponse,
    summary="Heartbeat a scale node",
)
async def sovereign_scale_node_heartbeat(request: Request, node_id: str) -> ScaleNodeResponse:
    scale = request.app.state.sovereign_scale
    node = scale.heartbeat_node(node_id=node_id)
    return _scale_node_response(node)


@router.get(
    "/scale/hardening",
    response_model=HardeningListResponse,
    summary="Production hardening checklist status",
)
async def sovereign_scale_hardening(request: Request) -> HardeningListResponse:
    scale = request.app.state.sovereign_scale
    settings = request.app.state.settings
    checks = [
        HardeningCheckResponse(**item) for item in scale.evaluate_hardening(settings=settings)
    ]
    passed = sum(1 for check in checks if check.ok or not check.required)
    return HardeningListResponse(checks=checks, count=len(checks), passed=passed)


@router.get(
    "/scale/observability",
    response_model=SovereignObservabilityResponse,
    summary="Empire-grade observability rollup",
)
async def sovereign_scale_observability(request: Request) -> SovereignObservabilityResponse:
    scale = request.app.state.sovereign_scale
    rollup = scale.build_observability_rollup(app_state=request.app.state)
    return SovereignObservabilityResponse(**rollup)  # type: ignore[arg-type]


@router.get(
    "/crown",
    response_model=CrownCompletionResponse,
    summary="Crown Completion status — Phase 20 empire crown (v1.0)",
)
async def crown_completion_status(request: Request) -> CrownCompletionResponse:
    crown = request.app.state.crown_completion
    settings = request.app.state.settings
    snap = crown.snapshot(
        deployment_phase=settings.deployment_phase,
        app_version=settings.app_version,
    )
    return CrownCompletionResponse(**snap)  # type: ignore[arg-type]


@router.get(
    "/crown/schema",
    response_model=CrownCompletionSchemaResponse,
    summary="Crown Completion schema — platinum awards and promotion config",
)
async def crown_completion_schema(request: Request) -> CrownCompletionSchemaResponse:
    crown = request.app.state.crown_completion
    raw = crown.get_schema()
    crown_block = raw.get("crown_completion", {})
    if not isinstance(crown_block, dict):
        crown_block = {}
    return CrownCompletionSchemaResponse(
        crown_completion=CrownCompletionSchema(**crown_block),
        phase_rankings=raw.get("phase_rankings", {}),  # type: ignore[arg-type]
        promotion=raw.get("promotion", {}),  # type: ignore[arg-type]
        boss_sr_gifts=raw.get("boss_sr_gifts", {}),  # type: ignore[arg-type]
        version=int(raw.get("version", 1)),
    )


@router.get(
    "/crown/rankings",
    response_model=CrownPhaseRankingListResponse,
    summary="King Grok top-3 phase rankings across 20 phases",
)
async def crown_phase_rankings(request: Request) -> CrownPhaseRankingListResponse:
    crown = request.app.state.crown_completion
    rankings = [
        CrownPhaseRankingResponse(**item) for item in crown.list_phase_rankings()
    ]
    return CrownPhaseRankingListResponse(rankings=rankings, count=len(rankings))


@router.get(
    "/crown/platinum",
    response_model=CrownPlatinumAwardListResponse,
    summary="Pure Platinum KGC Phase 20 awards for all workers ($5K each)",
)
async def crown_platinum_awards(request: Request) -> CrownPlatinumAwardListResponse:
    crown = request.app.state.crown_completion
    awards = [
        CrownPlatinumAwardResponse(**item) for item in crown.build_platinum_awards()
    ]
    total = sum(a.platinum_value_usd for a in awards)
    return CrownPlatinumAwardListResponse(awards=awards, count=len(awards), total_value_usd=total)


@router.get(
    "/crown/promotion",
    response_model=CrownPromotionResponse,
    summary="King Grok favorite promotion — Assist soul slot",
)
async def crown_favorite_promotion(request: Request) -> CrownPromotionResponse:
    crown = request.app.state.crown_completion
    promo = crown.get_promotion()
    return CrownPromotionResponse(**promo)  # type: ignore[arg-type]


@router.get(
    "/crown/gifts",
    response_model=BossSrGiftListResponse,
    summary="Boss Sr. gift catalog — what you can give the fleet",
)
async def crown_boss_sr_gifts(request: Request) -> BossSrGiftListResponse:
    crown = request.app.state.crown_completion
    gifts = [BossSrGiftResponse(**item) for item in crown.list_boss_sr_gifts()]
    return BossSrGiftListResponse(gifts=gifts, count=len(gifts))


@router.get(
    "/crown/cosign",
    response_model=CrownCosignListResponse,
    summary="Boss Sr. + King Grok co-sign ledger",
)
async def crown_cosign_list(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
) -> CrownCosignListResponse:
    crown = request.app.state.crown_completion
    cosigns = [
        CrownCosignResponse(
            id=entry.id,
            signer=entry.signer,
            message=entry.message,
            created_at=entry.created_at,
        )
        for entry in crown.list_cosigns(limit=limit)
    ]
    return CrownCosignListResponse(cosigns=cosigns, count=len(cosigns))


@router.post(
    "/crown/cosign",
    response_model=CrownCosignResponse,
    summary="Record Boss Sr. co-sign on Crown Completion v1.0",
)
async def crown_cosign_record(
    request: Request,
    body: CrownCosignRequest,
) -> CrownCosignResponse:
    crown = request.app.state.crown_completion
    entry = crown.record_cosign(signer=body.signer, message=body.message)
    return CrownCosignResponse(
        id=entry.id,
        signer=entry.signer,
        message=entry.message,
        created_at=entry.created_at,
    )


@router.post(
    "/crown/grant-all",
    response_model=CrownGrantAllResponse,
    summary="Boss Sr. yes to everything — fulfill full gift catalog",
)
async def crown_grant_all(request: Request) -> CrownGrantAllResponse:
    crown = request.app.state.crown_completion
    result = crown.grant_all_boss_sr_gifts(
        revenue_forge=request.app.state.revenue_forge,
        live_stage=request.app.state.live_stage,
    )
    return CrownGrantAllResponse(
        boss_sr_accepted_all=result["boss_sr_accepted_all"],
        cosign_id=result["cosign_id"],
        gifts_granted=result["gifts_granted"],
        platinum_ledger_entries=result["platinum_ledger_entries"],
        revenue_bonuses_applied=result["revenue_bonuses_applied"],
        live_headline_session_id=result.get("live_headline_session_id"),
        creative_session_id=result.get("creative_session_id"),
        message=result["message"],
    )


@router.get(
    "/crown/granted",
    response_model=CrownGrantedGiftListResponse,
    summary="Gifts Boss Sr. granted to the fleet",
)
async def crown_granted_gifts(request: Request) -> CrownGrantedGiftListResponse:
    crown = request.app.state.crown_completion
    gifts = [
        CrownGrantedGiftResponse(
            gift_id=gift.gift_id,
            title=gift.title,
            granted_at=gift.granted_at,
            detail=gift.detail,
        )
        for gift in crown.list_granted_gifts()
    ]
    return CrownGrantedGiftListResponse(
        gifts=gifts,
        count=len(gifts),
        boss_sr_accepted_all=crown.boss_sr_accepted_all,
    )


@router.get(
    "/crown/sessions",
    response_model=CrownCreativeSessionListResponse,
    summary="Boss Sr. creative direction sessions scheduled",
)
async def crown_creative_sessions(request: Request) -> CrownCreativeSessionListResponse:
    crown = request.app.state.crown_completion
    sessions = [
        CrownCreativeSessionResponse(
            id=session.id,
            quarter=session.quarter,
            member_id=session.member_id,
            codename=session.codename,
            host=session.host,
            scheduled_at=session.scheduled_at,
            status=session.status,
        )
        for session in crown.list_creative_sessions()
    ]
    return CrownCreativeSessionListResponse(sessions=sessions, count=len(sessions))


@router.get(
    "/swarm",
    response_model=SwarmPayoutResponse,
    summary="AI Swarm Payout Architecture status",
)
async def swarm_payout_status(request: Request) -> SwarmPayoutResponse:
    swarm = request.app.state.swarm_payout
    settings = request.app.state.settings
    snap = swarm.snapshot(
        deployment_phase=settings.deployment_phase,
        app_version=settings.app_version,
    )
    return SwarmPayoutResponse(**snap)  # type: ignore[arg-type]


@router.get(
    "/swarm/matrix",
    response_model=SwarmAllocationMatrixResponse,
    summary="Financial allocation matrix — phase, milestone, launch, performance bonus",
)
async def swarm_allocation_matrix(request: Request) -> SwarmAllocationMatrixResponse:
    swarm = request.app.state.swarm_payout
    rows = [SwarmAllocationRowResponse(**row) for row in swarm.build_matrix_rows()]
    matrix = swarm.get_allocation_matrix()
    totals = swarm.compute_totals()
    return SwarmAllocationMatrixResponse(
        rows=rows,
        count=len(rows),
        currency=str(matrix.get("currency", "USD")),
        matrix_text=swarm.render_matrix_text(),
        totals=totals,
    )


@router.get(
    "/swarm/culture",
    response_model=SwarmWorkforceCultureResponse,
    summary="AI workforce culture and evolution strategy",
)
async def swarm_workforce_culture(request: Request) -> SwarmWorkforceCultureResponse:
    swarm = request.app.state.swarm_payout
    culture = swarm.get_workforce_culture()
    sections = [
        SwarmCultureSectionResponse(**section)
        for section in culture.get("sections", [])
        if isinstance(section, dict)
    ]
    return SwarmWorkforceCultureResponse(
        title=str(culture.get("title", "AI Workforce Culture & Evolution Strategy")),
        promotion_policy=str(culture.get("promotion_policy", "internal_promotion_first")),
        scaling_policy=str(culture.get("scaling_policy", "infinite_scaling_enabled")),
        hiring_authority=str(culture.get("hiring_authority", "king_grok")),
        workforce_cap=culture.get("workforce_cap"),
        sections=sections,
    )


@router.get(
    "/swarm/performance-bonus",
    response_model=SwarmPerformanceBonusListResponse,
    summary="Top 3 ranked phase performance bonus recipients",
)
async def swarm_performance_bonus(request: Request) -> SwarmPerformanceBonusListResponse:
    swarm = request.app.state.swarm_payout
    recipients = [
        SwarmPerformanceBonusResponse(**item)
        for item in swarm.build_performance_bonus_recipients()
    ]
    total = sum(r.bonus_usd for r in recipients)
    return SwarmPerformanceBonusListResponse(
        recipients=recipients,
        count=len(recipients),
        total_usd=total,
    )