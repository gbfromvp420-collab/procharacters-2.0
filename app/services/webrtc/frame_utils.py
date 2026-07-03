import base64
import fractions
import logging

import av
from av import AudioFrame, VideoFrame

from app.services.webrtc.packets import AudioPacket

logger = logging.getLogger(__name__)

VIDEO_CLOCK_RATE = 90_000
AUDIO_PTIME = 0.020


def pts_ms_to_video_pts(pts_ms: int) -> int:
    return int(pts_ms * VIDEO_CLOCK_RATE / 1000)


def video_time_base() -> fractions.Fraction:
    return fractions.Fraction(1, VIDEO_CLOCK_RATE)


def jpeg_bytes_to_video_frame(
    jpeg_bytes: bytes,
    *,
    pts_ms: int,
    target_width: int | None = None,
    target_height: int | None = None,
) -> VideoFrame:
    codec = av.CodecContext.create("mjpeg", "r")
    decoded = codec.decode(av.Packet(jpeg_bytes))
    if not decoded:
        raise ValueError("MJPEG decoder returned no frames.")

    frame = decoded[0]
    if target_width and target_height:
        frame = frame.reformat(width=target_width, height=target_height, format="yuv420p")
    elif frame.format.name != "yuv420p":
        frame = frame.reformat(format="yuv420p")

    frame.pts = pts_ms_to_video_pts(pts_ms)
    frame.time_base = video_time_base()
    return frame


def jpeg_b64_to_video_frame(
    frame_b64: str,
    *,
    pts_ms: int,
    target_width: int | None = None,
    target_height: int | None = None,
) -> VideoFrame:
    return jpeg_bytes_to_video_frame(
        base64.b64decode(frame_b64),
        pts_ms=pts_ms,
        target_width=target_width,
        target_height=target_height,
    )


def pcm_b64_to_audio_packets(
    audio_b64: str,
    *,
    sample_rate: int,
    channels: int,
    start_pts_ms: int,
) -> list[AudioPacket]:
    pcm_bytes = base64.b64decode(audio_b64)
    samples_per_packet = max(1, int(sample_rate * AUDIO_PTIME))
    bytes_per_sample = 2
    packet_bytes = samples_per_packet * channels * bytes_per_sample

    packets: list[AudioPacket] = []
    start_pts_samples = int(start_pts_ms * sample_rate / 1000)
    offset = 0

    while offset < len(pcm_bytes):
        chunk = pcm_bytes[offset : offset + packet_bytes]
        if len(chunk) < packet_bytes:
            chunk = chunk.ljust(packet_bytes, b"\x00")

        packet_index = len(packets)
        pts_samples = start_pts_samples + packet_index * samples_per_packet
        pts_ms = start_pts_ms + int(packet_index * AUDIO_PTIME * 1000)

        packets.append(
            AudioPacket(
                pcm_bytes=chunk,
                sample_rate=sample_rate,
                channels=channels,
                pts_samples=pts_samples,
                pts_ms=pts_ms,
            )
        )
        offset += packet_bytes

    return packets


def audio_packet_to_frame(packet: AudioPacket) -> AudioFrame:
    layout = "mono" if packet.channels == 1 else "stereo"
    samples_per_channel = len(packet.pcm_bytes) // (2 * packet.channels)
    frame = AudioFrame(format="s16", layout=layout, samples=samples_per_channel)
    frame.planes[0].update(packet.pcm_bytes)
    frame.pts = packet.pts_samples
    frame.sample_rate = packet.sample_rate
    frame.time_base = fractions.Fraction(1, packet.sample_rate)
    return frame