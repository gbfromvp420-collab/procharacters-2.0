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
    OrchestrationStatusResponse,
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