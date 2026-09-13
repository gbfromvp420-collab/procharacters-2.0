"""In-process HTTP contract stubs for Innovation Lane 1 (Stage 1).

Config, verify_providers.py, and .env.example already describe localhost
LLM/TTS/Video HTTP endpoints. These helpers expose the same contracts from
the running FastAPI app so Stage 1 can finish without RunPod pods.
"""

from __future__ import annotations

from typing import Any

from fastapi import Request

from app.core.config import Settings

LOCAL_STUB_MARKER = "/api/v1/providers/local"

_RUNPOD_HOWTO: list[str] = [
    "Open https://www.runpod.io/console/pods (account required).",
    "Start or select three pods: LLM (vLLM / OpenAI-compatible), TTS (/synthesize), Video (/generate).",
    "On each pod click Connect → HTTP Services and copy the proxy URL.",
    "LLM URL must end with /v1 (chat/completions lives under that prefix).",
    "Paste the three URLs into Innovation · Wire and click Wire + live activate.",
    "Do not paste API keys into chat. Optional key stays in the Wire form or .env.",
    "No pods yet? That is a RunPod deploy, not a repo setting. Use local contract stubs first.",
]


def is_local_stub_url(endpoint: str) -> bool:
    return LOCAL_STUB_MARKER in (endpoint or "").lower()


def local_stub_urls_from_base(base_url: str) -> dict[str, str]:
    root = f"{base_url.rstrip('/')}/api/v1/providers/local"
    return {
        "llm_base_url": f"{root}/v1",
        "tts_base_url": root,
        "video_base_url": root,
    }


def local_stub_urls(request: Request) -> dict[str, str]:
    return local_stub_urls_from_base(str(request.base_url))


def stub_runtime_settings(settings: Settings) -> Settings:
    """Mocks with delays stripped so in-process contract stubs stay fast."""
    return settings.model_copy(
        update={
            "llm_provider": "mock",
            "tts_provider": "mock",
            "video_provider": "mock",
            "mock_realistic": False,
            "llm_mock_token_delay_ms": 0,
            "tts_mock_chunk_delay_ms": 0,
            "video_mock_frame_delay_ms": 0,
        }
    )


def detect_stage1_source(*, settings: Settings, wired: bool = False) -> str:
    urls = [settings.llm_base_url, settings.tts_base_url, settings.video_base_url]
    local_count = sum(1 for url in urls if is_local_stub_url(url))
    remote_modes = (
        settings.llm_provider == "openai_compatible",
        settings.tts_provider == "http",
        settings.video_provider == "http",
    )
    if all(remote_modes) and local_count == 3:
        return "local_stubs"
    if local_count and any(remote_modes):
        return "mixed"
    if all(remote_modes) and (wired or local_count == 0):
        return "runpod"
    return "none"


def runpod_howto() -> list[str]:
    return list(_RUNPOD_HOWTO)


def stage1_blocker(*, ready: bool, source: str, configured: int) -> str:
    if ready and source == "local_stubs":
        return (
            "Stage 1 local complete. Swap in RunPod Connect URLs when pods exist. "
            "You can advance to Soul."
        )
    if ready and source == "runpod":
        return "Stage 1 live. Real providers are wired."
    if ready and source == "mixed":
        return "Stage 1 mixed — replace leftover local stub URLs with RunPod proxies."
    missing = 3 - configured
    return (
        f"Stage 1 needs {missing} more HTTP provider URL(s). "
        "Use local contract stubs now, or paste RunPod Connect proxy URLs."
    )


def stage1_status(*, ready: bool, source: str) -> str:
    if ready and source == "local_stubs":
        return "ready_local"
    if ready and source == "runpod":
        return "live"
    if ready:
        return "ready_mixed"
    return "in_progress"


def local_stub_report(request: Request | None = None, *, base_url: str = "") -> dict[str, Any]:
    urls = local_stub_urls(request) if request is not None else local_stub_urls_from_base(base_url)
    return {
        "available": True,
        "kind": "local_contract_stubs",
        "note": (
            "Same LLM/TTS/Video contracts as RunPod, served from this process. "
            "Unblocks Stage 1 without pods."
        ),
        **urls,
        "runpod_console": "https://www.runpod.io/console/pods",
        "howto": runpod_howto(),
    }
