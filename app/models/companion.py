from pydantic import BaseModel, Field

from app.models.llm import ChatMessage


class CompanionConfig(BaseModel):
    avatar_id: str
    voice: str
    system_prompt: str


class CompanionConfigUpdate(BaseModel):
    avatar_id: str | None = None
    voice: str | None = None
    system_prompt: str | None = None


class ConversationHistoryResponse(BaseModel):
    messages: list[ChatMessage] = Field(default_factory=list)
    turn_count: int = Field(
        description="Number of completed user/assistant turns in stored history.",
    )