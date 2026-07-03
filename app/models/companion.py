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


class CompanionCatalogResponse(BaseModel):
    avatars: list[AvatarInfo]
    voices: list[VoiceInfo]
    prompt_presets: list[PromptPreset]


class CompanionConfig(BaseModel):
    avatar_id: str
    voice: str
    system_prompt: str
    turn_count: int = Field(
        default=0,
        description="Number of completed user/assistant turns in stored history.",
    )
    created_at: str = Field(description="ISO-8601 UTC timestamp when the session was created.")
    last_active_at: str = Field(
        description="ISO-8601 UTC timestamp of the most recent companion activity.",
    )


class CompanionSessionSummary(BaseModel):
    id: str
    turn_count: int
    last_active_at: str
    avatar_id: str


class CompanionConfigUpdate(BaseModel):
    avatar_id: str | None = None
    voice: str | None = None
    system_prompt: str | None = None


class ConversationHistoryResponse(BaseModel):
    messages: list[ChatMessage] = Field(default_factory=list)
    turn_count: int = Field(
        description="Number of completed user/assistant turns in stored history.",
    )