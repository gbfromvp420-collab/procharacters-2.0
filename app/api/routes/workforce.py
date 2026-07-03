from fastapi import APIRouter

from app.models.workforce import (
    WorkforceLeaderboardResponse,
    WorkforceMemberResponse,
    WorkforceRosterResponse,
)
from app.workforce.roster import get_leaderboard, get_roster

router = APIRouter(prefix="/workforce", tags=["workforce"])


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