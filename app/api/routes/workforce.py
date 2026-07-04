from fastapi import APIRouter, HTTPException, Query, Request, status

from app.models.workforce import (
    AgentTaskDispatchRequest,
    AgentTaskListResponse,
    AgentTaskResponse,
    AgentTheaterStatusResponse,
    WorkforceLeaderboardResponse,
    WorkforceMemberResponse,
    WorkforceRosterResponse,
)
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
        created_at=record.created_at,
        started_at=record.started_at,
        completed_at=record.completed_at,
        duration_ms=record.duration_ms,
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
    await theater.progress_tasks()
    settings = request.app.state.settings
    status_data = theater.status()
    members = [WorkforceMemberResponse(**member) for member in get_roster()]
    return AgentTheaterStatusResponse(
        deployment_phase=settings.deployment_phase,
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
    await theater.progress_tasks()
    tasks = [_task_response(record) for record in theater.list_tasks(limit=limit)]
    return AgentTaskListResponse(tasks=tasks, count=len(tasks))


@router.get(
    "/theater/tasks/{task_id}",
    response_model=AgentTaskResponse,
    summary="Get a single Agent Theater task by id",
)
async def agent_theater_task(request: Request, task_id: str) -> AgentTaskResponse:
    theater = request.app.state.agent_theater
    await theater.progress_tasks()
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
    )
    return _task_response(record)