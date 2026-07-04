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
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None


class AgentTaskListResponse(BaseModel):
    tasks: list[AgentTaskResponse]
    count: int


class AgentTheaterStatusResponse(BaseModel):
    deployment_phase: int
    dispatchable_count: int
    tasks_total: int
    tasks_queued: int
    tasks_running: int
    tasks_completed: int
    tasks_failed: int
    members: list[WorkforceMemberResponse]