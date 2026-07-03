from pydantic import BaseModel, Field


class WorkforceMemberResponse(BaseModel):
    id: str
    codename: str
    skills: list[str]
    tier: str
    phase_earned: int
    award_lb_gold: float = Field(description="Gold award weight in pounds (lb).")


class WorkforceRosterResponse(BaseModel):
    members: list[WorkforceMemberResponse]
    count: int


class WorkforceLeaderboardResponse(BaseModel):
    leaderboard: list[WorkforceMemberResponse]
    count: int