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


class ProviderContractSpec(BaseModel):
    provider: ProviderName
    endpoint_path: str
    method: str
    request_fields: list[str]
    response_fields: list[str]


class ProviderForgeEntry(BaseModel):
    provider: ProviderName
    mode: str
    endpoint: str
    probe_status: ProviderHealthStatus
    contract_ok: bool
    smoke_ok: bool | None = Field(
        default=None,
        description="Set when live_smoke ran; None when only static/probe checks ran.",
    )
    message: str
    spec: ProviderContractSpec


class ProviderForgeResponse(BaseModel):
    forge_ok: bool
    live_smoke: bool
    llm: ProviderForgeEntry
    tts: ProviderForgeEntry
    video: ProviderForgeEntry