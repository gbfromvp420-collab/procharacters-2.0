from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(..., min_length=1)
    session_id: str | None = Field(
        default=None,
        description="Optional client session for downstream TTS/video sync.",
    )
    max_tokens: int | None = None
    temperature: float | None = None


class StreamTokenEvent(BaseModel):
    type: Literal["token"] = "token"
    content: str
    index: int


class StreamDoneEvent(BaseModel):
    type: Literal["done"] = "done"
    session_id: str | None = None
    finish_reason: str | None = None
    token_count: int


class StreamErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    message: str