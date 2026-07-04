"""RunPod wiring — single JSON file flips mock → real providers."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.services.providers.contracts import is_placeholder_endpoint

logger = logging.getLogger(__name__)

_DEFAULT_PATH = "data/runpod_wiring.json"


def load_runpod_wiring(path: str = _DEFAULT_PATH) -> dict[str, Any]:
    file_path = Path(path)
    if not file_path.is_file():
        return {"enabled": False}
    try:
        raw = json.loads(file_path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            return raw
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed to load runpod wiring %s: %s", path, exc)
    return {"enabled": False}


def save_runpod_wiring(data: dict[str, Any], path: str = _DEFAULT_PATH) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _block_ready(block: dict[str, Any] | None, *, remote_modes: tuple[str, ...]) -> bool:
    if not isinstance(block, dict):
        return False
    mode = str(block.get("provider", ""))
    if mode not in remote_modes:
        return False
    base_url = str(block.get("base_url", "")).strip()
    return bool(base_url) and not is_placeholder_endpoint(base_url)


def wiring_readiness(wiring: dict[str, Any]) -> dict[str, Any]:
    llm = wiring.get("llm", {}) if isinstance(wiring.get("llm"), dict) else {}
    tts = wiring.get("tts", {}) if isinstance(wiring.get("tts"), dict) else {}
    video = wiring.get("video", {}) if isinstance(wiring.get("video"), dict) else {}
    llm_ok = _block_ready(llm, remote_modes=("openai_compatible",))
    tts_ok = _block_ready(tts, remote_modes=("http",))
    video_ok = _block_ready(video, remote_modes=("http",))
    enabled = bool(wiring.get("enabled"))
    can_wire = llm_ok and tts_ok and video_ok
    return {
        "enabled": enabled,
        "wired": enabled and can_wire,
        "llm_ready": llm_ok,
        "tts_ready": tts_ok,
        "video_ready": video_ok,
        "all_ready": can_wire,
        "pod_label": str(wiring.get("pod_label", "")),
    }


def apply_runpod_wiring(settings: Settings) -> Settings:
    """Overlay provider settings when runpod_wiring.json is enabled with real URLs."""
    wiring = load_runpod_wiring(settings.runpod_wiring_path)
    readiness = wiring_readiness(wiring)
    if not readiness["wired"]:
        return settings

    llm = wiring.get("llm", {})
    tts = wiring.get("tts", {})
    video = wiring.get("video", {})
    if not isinstance(llm, dict) or not isinstance(tts, dict) or not isinstance(video, dict):
        return settings

    updates: dict[str, Any] = {
        "llm_provider": "openai_compatible",
        "llm_base_url": str(llm.get("base_url", settings.llm_base_url)).rstrip("/"),
        "llm_api_key": str(llm.get("api_key", settings.llm_api_key)),
        "tts_provider": "http",
        "tts_base_url": str(tts.get("base_url", settings.tts_base_url)).rstrip("/"),
        "tts_api_key": str(tts.get("api_key", settings.tts_api_key)),
        "video_provider": "http",
        "video_base_url": str(video.get("base_url", settings.video_base_url)).rstrip("/"),
        "video_api_key": str(video.get("api_key", settings.video_api_key)),
    }
    if llm.get("model"):
        updates["llm_model"] = str(llm["model"])
    if "provider_gate_enabled" in wiring:
        updates["provider_gate_enabled"] = bool(wiring["provider_gate_enabled"])
    if "provider_gate_allow_degraded" in wiring:
        updates["provider_gate_allow_degraded"] = bool(wiring["provider_gate_allow_degraded"])

    logger.info(
        "RunPod wiring active — LLM=%s TTS=%s VIDEO=%s",
        updates["llm_base_url"],
        updates["tts_base_url"],
        updates["video_base_url"],
    )
    return settings.model_copy(update=updates)


def build_wiring_report(settings: Settings) -> dict[str, Any]:
    wiring = load_runpod_wiring(settings.runpod_wiring_path)
    readiness = wiring_readiness(wiring)
    effective = apply_runpod_wiring(settings)
    return {
        "wiring_path": settings.runpod_wiring_path,
        "readiness": readiness,
        "notes": str(wiring.get("notes", "")),
        "effective_providers": {
            "llm": {
                "provider": effective.llm_provider,
                "base_url": effective.llm_base_url,
                "model": effective.llm_model,
            },
            "tts": {
                "provider": effective.tts_provider,
                "base_url": effective.tts_base_url,
            },
            "video": {
                "provider": effective.video_provider,
                "base_url": effective.video_base_url,
            },
        },
        "env_snippet": render_env_snippet(wiring) if readiness["all_ready"] else None,
    }


def render_env_snippet(wiring: dict[str, Any]) -> str:
    llm = wiring.get("llm", {}) if isinstance(wiring.get("llm"), dict) else {}
    tts = wiring.get("tts", {}) if isinstance(wiring.get("tts"), dict) else {}
    video = wiring.get("video", {}) if isinstance(wiring.get("video"), dict) else {}
    lines = [
        "# RunPod wiring — paste into .env",
        "LLM_PROVIDER=openai_compatible",
        f"LLM_BASE_URL={llm.get('base_url', '')}",
        f"LLM_API_KEY={llm.get('api_key', '')}",
        f"LLM_MODEL={llm.get('model', 'meta-llama/Meta-Llama-3-8B-Instruct')}",
        "TTS_PROVIDER=http",
        f"TTS_BASE_URL={tts.get('base_url', '')}",
        f"TTS_API_KEY={tts.get('api_key', '')}",
        "VIDEO_PROVIDER=http",
        f"VIDEO_BASE_URL={video.get('base_url', '')}",
        f"VIDEO_API_KEY={video.get('api_key', '')}",
        f"PROVIDER_GATE_ENABLED={str(wiring.get('provider_gate_enabled', True)).lower()}",
    ]
    return "\n".join(lines)


def update_wiring_urls(
    *,
    path: str,
    llm_base_url: str | None = None,
    tts_base_url: str | None = None,
    video_base_url: str | None = None,
    api_key: str | None = None,
    llm_api_key: str | None = None,
    tts_api_key: str | None = None,
    video_api_key: str | None = None,
    enabled: bool | None = None,
) -> dict[str, Any]:
    wiring = load_runpod_wiring(path)
    for block_name, url in (
        ("llm", llm_base_url),
        ("tts", tts_base_url),
        ("video", video_base_url),
    ):
        if url is not None:
            block = wiring.setdefault(block_name, {})
            if isinstance(block, dict):
                block["base_url"] = url.strip().rstrip("/")
                if block_name == "llm" and not block.get("provider"):
                    block["provider"] = "openai_compatible"
                if block_name in ("tts", "video") and not block.get("provider"):
                    block["provider"] = "http"

    shared_key = api_key
    if shared_key is not None:
        for block_name in ("llm", "tts", "video"):
            block = wiring.get(block_name, {})
            if isinstance(block, dict):
                block["api_key"] = shared_key
    for block_name, key in (
        ("llm", llm_api_key),
        ("tts", tts_api_key),
        ("video", video_api_key),
    ):
        if key is not None:
            block = wiring.setdefault(block_name, {})
            if isinstance(block, dict):
                block["api_key"] = key

    if enabled is not None:
        wiring["enabled"] = enabled
    elif wiring_readiness(wiring)["all_ready"]:
        wiring["enabled"] = True

    save_runpod_wiring(wiring, path)
    return wiring