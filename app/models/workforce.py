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