"""Canonical HTTP provider contract specifications (RunPod / vLLM / MuseTalk)."""

from __future__ import annotations

from typing import TypedDict


class ContractSpecDict(TypedDict):
    endpoint_path: str
    method: str
    request_fields: list[str]
    response_fields: list[str]
    remote_modes: tuple[str, ...]


PROVIDER_CONTRACTS: dict[str, ContractSpecDict] = {
    "llm": {
        "endpoint_path": "/chat/completions",
        "method": "POST",
        "request_fields": [
            "model",
            "messages",
            "stream",
            "max_tokens",
            "temperature",
        ],
        "response_fields": [
            "choices[].delta.content (SSE)",
            "data: [DONE]",
        ],
        "remote_modes": ("openai_compatible",),
    },
    "tts": {
        "endpoint_path": "/synthesize",
        "method": "POST",
        "request_fields": [
            "text",
            "voice",
            "format",
            "sample_rate",
            "channels",
        ],
        "response_fields": [
            "audio_b64",
            "sample_rate (optional)",
            "channels (optional)",
            "raw PCM fallback",
        ],
        "remote_modes": ("http",),
    },
    "video": {
        "endpoint_path": "/generate",
        "method": "POST",
        "request_fields": [
            "audio_b64",
            "sample_rate",
            "channels",
            "duration_ms",
            "avatar_id",
            "fps",
            "start_pts_ms",
            "start_frame_index",
        ],
        "response_fields": [
            "frames[].frame_index",
            "frames[].pts_ms",
            "frames[].frame_b64",
            "width (optional)",
            "height (optional)",
        ],
        "remote_modes": ("http",),
    },
}

_PLACEHOLDER_MARKERS = (
    "your-runpod",
    "your-",
    "example.com",
    "changeme",
    "placeholder",
)


def is_placeholder_endpoint(endpoint: str) -> bool:
    lowered = endpoint.lower().strip()
    if not lowered or lowered in {"http://", "https://"}:
        return True
    return any(marker in lowered for marker in _PLACEHOLDER_MARKERS)