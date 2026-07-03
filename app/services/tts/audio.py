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
    """Generate synthetic PCM16 mono tone. Duration scales with text.

    Realism improvements:
    - Base duration + small variance derived from text content (hash) for variable chunk lengths
    - Frequency modulated slightly per "segment" to avoid pure constant tone boredom
    - Minimum duration ensures non-empty audio for very short chunks
    """
    # Variable length: base + deterministic jitter from content
    base_dur = max(0.12, (len(text) * ms_per_char) / 1000.0)
    jitter = ((hash(text) % 11) - 5) * 0.008  # +/- ~40ms
    duration_sec = max(0.08, base_dur + jitter)

    sample_count = int(sample_rate * duration_sec)
    base_freq = 220.0 + (len(text) % 7) * 48.0
    amplitude = 11000

    frames = bytearray()
    for index in range(sample_count):
        # Gentle frequency wobble for "more natural" mock audio
        wobble = 1.0 + 0.03 * math.sin(2 * math.pi * index / (sample_rate * 0.4))
        freq = base_freq * wobble
        sample = int(
            amplitude * math.sin(2 * math.pi * freq * index / sample_rate)
        )
        frames.extend(struct.pack("<h", sample))

    return bytes(frames)