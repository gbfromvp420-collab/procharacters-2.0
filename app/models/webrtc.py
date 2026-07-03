from typing import Literal

from pydantic import BaseModel, Field


class RTCSessionDescriptionPayload(BaseModel):
    type: Literal["offer", "answer"]
    sdp: str


class WebRTCOfferRequest(BaseModel):
    sdp: str = Field(..., description="SDP offer from the client peer.")
    type: Literal["offer"] = "offer"
    session_id: str | None = Field(
        default=None,
        description="Optional existing session to renegotiate.",
    )


class WebRTCAnswerResponse(BaseModel):
    session_id: str
    sdp: str
    type: Literal["answer"] = "answer"


class IceCandidateRequest(BaseModel):
    session_id: str
    candidate: str
    sdp_mid: str | None = None
    sdp_mline_index: int | None = None


class SessionCreatedResponse(BaseModel):
    session_id: str
    ice_servers: list[dict[str, str | list[str]]]


class ActiveSessionsResponse(BaseModel):
    sessions: list[str]
    count: int