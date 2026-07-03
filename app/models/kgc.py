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


class KGCAuditEntry(BaseModel):
    timestamp: str
    action: str
    actor: str
    detail: str
    result: str


class KGCAuditResponse(BaseModel):
    entries: list[KGCAuditEntry]
    count: int


class KGCPoliciesResponse(BaseModel):
    default_relationship_mode: str = ""
    default_system_prompt: str = ""
    auto_prune_enabled: bool = True


class KGCPoliciesUpdate(BaseModel):
    default_relationship_mode: str | None = None
    default_system_prompt: str | None = None
    auto_prune_enabled: bool | None = None


class KGCFleetBackupResponse(BaseModel):
    version: str
    exported_at: str
    companion_sessions: dict[str, Any]
    policies: dict[str, Any]
    audit_tail: list[KGCAuditEntry]


class KGCFleetRestoreRequest(BaseModel):
    version: str | None = None
    exported_at: str | None = None
    companion_sessions: dict[str, Any]
    policies: dict[str, Any] | None = None
    audit_tail: list[dict[str, Any]] | None = None


class KGCFleetRestoreResponse(BaseModel):
    sessions_merged: int
    sessions_total: int


class KGCCloneRequest(BaseModel):
    source_session_id: str
    target_session_id: str | None = None


class KGCCloneResponse(BaseModel):
    source_session_id: str
    target_session_id: str


class KGCImportRequest(BaseModel):
    session_id: str
    data: dict[str, Any]


class KGCImportResponse(BaseModel):
    session_id: str
    imported: bool