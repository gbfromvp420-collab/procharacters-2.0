from pydantic import BaseModel, Field

from app.models.llm import ChatMessage


class AvatarInfo(BaseModel):
    id: str
    label: str
    description: str
    accent_color: str = Field(description="Hex accent color for UI theming")
    emoji: str


class VoiceInfo(BaseModel):
    id: str
    label: str
    description: str


class PromptPreset(BaseModel):
    id: str
    label: str
    prompt: str


class RelationshipModeInfo(BaseModel):
    id: str
    label: str
    description: str
    system_prompt_overlay: str


class CompanionCatalogResponse(BaseModel):
    avatars: list[AvatarInfo]
    voices: list[VoiceInfo]
    prompt_presets: list[PromptPreset]
    relationship_modes: list[RelationshipModeInfo] = Field(default_factory=list)


class CompanionConfig(BaseModel):
    avatar_id: str
    voice: str
    system_prompt: str
    relationship_mode: str = Field(
        default="",
        description="Optional intimacy/personality mode id (e.g. friendly, romantic).",
    )
    bond_score: int = Field(
        default=0,
        ge=0,
        le=100,
        description="Companion affinity score for this session (0-100).",
    )
    memory_summary: str = Field(
        default="",
        description="Truncated preview of rolling conversation memory summary.",
    )
    turn_count: int = Field(
        default=0,
        description="Number of completed user/assistant turns in stored history.",
    )
    created_at: str = Field(description="ISO-8601 UTC timestamp when the session was created.")
    last_active_at: str = Field(
        description="ISO-8601 UTC timestamp of the most recent companion activity.",
    )
    soul_stage: str = Field(default="acquaintance", description="Innovation Lane 2 soul stage id.")
    soul_stage_label: str = Field(default="Acquaintance", description="Soul stage display label.")
    soul_memory_count: int = Field(default=0, ge=0, description="Pinned soul memories for this session.")


class CompanionSessionSummary(BaseModel):
    id: str
    turn_count: int
    last_active_at: str
    avatar_id: str
    bond_score: int = Field(default=0, ge=0, le=100)


class CompanionConfigUpdate(BaseModel):
    avatar_id: str | None = None
    voice: str | None = None
    system_prompt: str | None = None
    relationship_mode: str | None = None


class CompanionHeartbeatResponse(BaseModel):
    session_id: str
    status: str = "active"
    turn_count: int
    last_active_at: str
    avatar_id: str
    relationship_mode: str = ""
    bond_score: int = Field(
        default=0,
        ge=0,
        le=100,
        description="Current affinity bond score (0–100).",
    )


class ConversationHistoryResponse(BaseModel):
    messages: list[ChatMessage] = Field(default_factory=list)
    turn_count: int = Field(
        description="Number of completed user/assistant turns in stored history.",
    )


class BondMilestoneInfo(BaseModel):
    id: str
    label: str
    description: str
    bond_threshold: int = Field(ge=0, le=100)


class BondMilestonesCatalogResponse(BaseModel):
    milestones: list[BondMilestoneInfo]


class PresenceBondTier(BaseModel):
    id: str
    label: str
    min_bond: int = Field(ge=0, le=100)
    aura_color: str
    glow_intensity: float = Field(ge=0.0, le=1.0)


class PresenceConfigResponse(BaseModel):
    celebration_enabled: bool = True
    voice_input_enabled: bool = True
    voice_input_hint: str = ""
    bond_tiers: list[PresenceBondTier] = Field(default_factory=list)


class BondMilestoneEvent(BaseModel):
    type: str = "bond_milestone"
    milestone_id: str
    label: str
    bond_score: int = Field(ge=0, le=100)


class SoulMemoryItem(BaseModel):
    id: str
    title: str
    body: str
    source: str
    created_at: str


class CompanionBundleResponse(BaseModel):
    session_id: str
    avatar_id: str
    voice: str
    system_prompt: str
    relationship_mode: str = ""
    bond_score: int = Field(default=0, ge=0, le=100)
    milestones_unlocked: list[str] = Field(default_factory=list)
    memory_summary: str = ""
    soul_memories: list[SoulMemoryItem] = Field(default_factory=list)
    messages: list[ChatMessage] = Field(default_factory=list)
    turn_count: int = Field(default=0, ge=0)
    created_at: str
    last_active_at: str


class CloneSessionResponse(BaseModel):
    session_id: str
    config: CompanionConfig


class ImportSessionRequest(BaseModel):
    session_id: str | None = Field(
        default=None,
        description="Optional target session id; a new uuid is used if omitted or colliding.",
    )
    avatar_id: str | None = None
    voice: str | None = None
    system_prompt: str | None = None
    relationship_mode: str | None = None
    bond_score: int | None = Field(default=None, ge=0, le=100)
    milestones_unlocked: list[str] | None = None
    memory_summary: str | None = None
    soul_memories: list[SoulMemoryItem] | None = None
    messages: list[ChatMessage] | None = None
    turn_count: int | None = Field(default=None, ge=0)
    created_at: str | None = None
    last_active_at: str | None = None
    config: CompanionConfig | None = Field(
        default=None,
        description="Nested config block from bundle export (alternative flat fields).",
    )


class ImportSessionResponse(BaseModel):
    session_id: str


class SoulMemoryPinRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(default="", max_length=2000)
    source: str = Field(default="pinned", max_length=32)


class SoulCheckinResponse(BaseModel):
    greeting: str
    returning: bool
    hours_away: float
    soul_stage: str
    soul_stage_label: str
    bond_score: int
    relationship_mode: str = ""
    memory_count: int
    latest_memory: SoulMemoryItem | None = None
    checkin_threshold_hours: float


class SoulSnapshotResponse(BaseModel):
    session_id: str
    soul_stage: str
    soul_stage_label: str
    bond_score: int
    relationship_mode: str = ""
    memory_count: int
    memories: list[SoulMemoryItem]
    checkin: SoulCheckinResponse
    overlay: str


class SoulMemoryListResponse(BaseModel):
    memories: list[SoulMemoryItem]
    count: int
    session_id: str