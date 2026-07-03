from typing import Literal

from pydantic import BaseModel, Field


ProviderName = Literal["llm", "tts", "video"]
ProviderHealthStatus = Literal["ok", "degraded", "unreachable"]


class ProviderStatus(BaseModel):
    provider: ProviderName
    mode: str = Field(description="Configured provider mode, e.g. mock, http, openai_compatible")
    status: ProviderHealthStatus
    latency_ms: int = Field(ge=0)
    endpoint: str
    message: str


class ProvidersStatusResponse(BaseModel):
    llm: ProviderStatus
    tts: ProviderStatus
    video: ProviderStatus