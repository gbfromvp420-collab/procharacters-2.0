from typing import Any, Literal

from pydantic import BaseModel, Field


class LivenessResponse(BaseModel):
    status: Literal["alive"] = "alive"
    service: str
    version: str
    deployment_phase: int


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    service: str
    version: str
    deployment_phase: int
    checks: dict[str, Any] = Field(default_factory=dict)