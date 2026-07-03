from typing import Literal

from pydantic import BaseModel, Field


class VideoSyncRequest(BaseModel):
    audio_b64: str = Field(..., min_length=1)
    sample_rate: int = 24000
    channels: int = 1
    duration_ms: int = Field(..., gt=0)
    audio_chunk_index: int = 0
    session_id: str | None = None
    avatar_id: str | None = None


class VideoFrameEvent(BaseModel):
    type: Literal["video_frame"] = "video_frame"
    frame_index: int
    audio_chunk_index: int
    pts_ms: int
    frame_b64: str
    format: Literal["jpeg"] = "jpeg"
    width: int
    height: int
    session_id: str | None = None


class VideoSyncDoneEvent(BaseModel):
    type: Literal["video_done"] = "video_done"
    session_id: str | None = None
    frame_count: int
    total_duration_ms: int


class VideoSyncErrorEvent(BaseModel):
    type: Literal["video_error"] = "video_error"
    message: str