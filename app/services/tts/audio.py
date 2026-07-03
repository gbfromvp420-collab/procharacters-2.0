import base64
import math
import struct


def pcm_duration_ms(pcm_bytes: bytes, sample_rate: int, channels: int) -> int:
    bytes_per_sample = 2
    frame_count = len(pcm_bytes) // (bytes_per_sample * channels)
    if frame_count == 0:
        return 0
    return int((frame_count / sample_rate) * 1000)


def encode_pcm_b64(pcm_bytes: bytes) -> str:
    return base64.b64encode(pcm_bytes).decode("ascii")


def generate_mock_pcm(
    text: str,
    *,
    sample_rate: int,
    ms_per_char: int = 45,
) -> bytes:
    """Generate a short PCM16 mono tone scaled to text length (dev placeholder)."""
    duration_sec = max(0.12, (len(text) * ms_per_char) / 1000)
    sample_count = int(sample_rate * duration_sec)
    frequency = 220.0 + (len(text) % 5) * 55.0
    amplitude = 12000

    frames = bytearray()
    for index in range(sample_count):
        sample = int(
            amplitude * math.sin(2 * math.pi * frequency * index / sample_rate)
        )
        frames.extend(struct.pack("<h", sample))

    return bytes(frames)