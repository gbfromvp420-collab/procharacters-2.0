from typing import Literal

from pydantic import BaseModel, Field


class SynthesizeRequest(BaseModel):
    text: str = Field(..., min_length=1)
    session_id: str | None = None
    voice: str | None = None


class AudioChunkEvent(BaseModel):
    type: Literal["audio"] = "audio"
    chunk_index: int
    text: str
    audio_b64: str
    sample_rate: int
    channels: int
    encoding: Literal["pcm_s16le"] = "pcm_s16le"
    duration_ms: int
    session_id: str | None = None


class TTSDoneEvent(BaseModel):
    type: Literal["tts_done"] = "tts_done"
    session_id: str | None = None
    chunk_count: int
    total_duration_ms: int


class TTSErrorEvent(BaseModel):
    type: Literal["tts_error"] = "tts_error"
    message: str