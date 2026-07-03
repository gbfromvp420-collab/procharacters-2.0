"""KGC Executive Command Layer response models."""

from typing import Any

from pydantic import BaseModel, Field


class KGCWebRTCSessionDetail(BaseModel):
    session_id: str
    created_at: str
    connection_state: str
    ice_connection_state: str
    ice_gathering_state: str


class KGCDashboardResponse(BaseModel):
    app_version: str
    uptime_seconds: float
    metrics_snapshot: dict[str, int]
    active_webrtc_sessions: int
    webrtc_sessions: list[KGCWebRTCSessionDetail]
    companion_sessions_count: int
    companion_total_turns: int
    companion_avg_bond_score: float
    providers_summary: dict[str, Any]
    workforce_count: int
    workforce_total_gold_lb: float
    kgc_status: str = Field(default="operational")


class KGCFleetEntry(BaseModel):
    session_id: str
    webrtc_active: bool
    connection_state: str | None = None
    ice_connection_state: str | None = None
    ice_gathering_state: str | None = None
    webrtc_created_at: str | None = None
    companion_active: bool
    turn_count: int = 0
    bond_score: int = Field(default=0, ge=0, le=100)
    avatar_id: str | None = None
    last_active_at: str | None = None


class KGCFleetResponse(BaseModel):
    fleet: list[KGCFleetEntry]
    count: int


class KGCPruneResponse(BaseModel):
    pruned: int
    ttl_hours: int