from dataclasses import dataclass


@dataclass(frozen=True)
class AudioPacket:
    pcm_bytes: bytes
    sample_rate: int
    channels: int
    pts_samples: int
    pts_ms: int


@dataclass(frozen=True)
class VideoPacket:
    jpeg_bytes: bytes
    width: int
    height: int
    frame_index: int
    pts_ms: int