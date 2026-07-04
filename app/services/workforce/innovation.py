"""Innovation lanes — post-v1.0 product roadmap (Real, Soul, $, Live)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from app.services.providers.contracts import is_placeholder_endpoint

logger = logging.getLogger(__name__)

_DEFAULT_SCHEMA_PATH = "data/innovation_lanes.json"

_RUNPOD_ENV_CHECKLIST: list[dict[str, str]] = [
    {
        "key": "LLM_PROVIDER",
        "value": "openai_compatible",
        "note": "Switch from mock to OpenAI-compatible stream",
    },
    {
        "key": "LLM_BASE_URL",
        "value": "https://YOUR-POD/v1",
        "note": "RunPod vLLM or compatible endpoint",
    },
    {
        "key": "LLM_API_KEY",
        "value": "(your key)",
        "note": "RunPod API key if required",
    },
    {
        "key": "TTS_PROVIDER",
        "value": "http",
        "note": "Remote TTS synthesis",
    },
    {
        "key": "TTS_BASE_URL",
        "value": "https://YOUR-TTS-POD",
        "note": "POST /synthesize contract",
    },
    {
        "key": "VIDEO_PROVIDER",
        "value": "http",
        "note": "Remote MuseTalk lip-sync",
    },
    {
        "key": "VIDEO_BASE_URL",
        "value": "https://YOUR-VIDEO-POD",
        "note": "POST /generate contract",
    },
    {
        "key": "PROVIDER_GATE_ENABLED",
        "value": "true",
        "note": "Block perform when providers down",
    },
]

_DEFAULT_SCHEMA: dict[str, Any] = {
    "active_lane": "real_providers",
    "lanes": [
        {
            "id": "real_providers",
            "rank": 1,
            "label": "Real",
            "title": "Real Provider Live",
            "summary": "RunPod LLM → TTS → MuseTalk — mock was the forge, real is the stage.",
            "status": "in_progress",
        },
        {
            "id": "companion_soul",
            "rank": 2,
            "label": "Soul",
            "title": "Companion Depth",
            "summary": "Relationship modes, bond, memory, presence — Assist's platinum lane.",
            "status": "queued",
        },
        {
            "id": "characters_revenue",
            "rank": 3,
            "label": "$",
            "title": "Characters + Revenue",
            "summary": "NSM onboarding, avatar bind, ledger, donations, subscription share.",
            "status": "queued",
        },
        {
            "id": "live_launch",
            "rank": 4,
            "label": "Live",
            "title": "Live Launch",
            "summary": "Cam chat, ticketed shows, Assist headline, public v1.0.",
            "status": "queued",
        },
    ],
    "version": 1,
}


class InnovationLanes:
    """Post-v1.0 innovation lane status and Real Provider readiness."""

    def __init__(self, *, schema_path: str = _DEFAULT_SCHEMA_PATH) -> None:
        self._schema_path = schema_path
        self._schema = self._load_schema()

    def _load_schema(self) -> dict[str, Any]:
        path = Path(self._schema_path)
        if path.is_file():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    return raw
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning("Failed to load innovation lanes %s: %s", path, exc)
        return dict(_DEFAULT_SCHEMA)

    def get_schema(self) -> dict[str, Any]:
        return dict(self._schema)

    def list_lanes(self) -> list[dict[str, Any]]:
        lanes = self._schema.get("lanes", [])
        if not isinstance(lanes, list):
            return []
        return sorted(
            [dict(item) for item in lanes if isinstance(item, dict)],
            key=lambda row: int(row.get("rank", 99)),
        )

    def get_active_lane(self) -> dict[str, Any] | None:
        active_id = self._schema.get("active_lane", "real_providers")
        for lane in self.list_lanes():
            if lane.get("id") == active_id:
                return lane
        return self.list_lanes()[0] if self.list_lanes() else None

    def build_real_provider_readiness(self, *, settings: Any) -> dict[str, Any]:
        providers: list[dict[str, Any]] = []
        remote_count = 0
        configured_count = 0

        for name, mode_attr, url_attr, remote_modes in (
            ("llm", "llm_provider", "llm_base_url", ("openai_compatible",)),
            ("tts", "tts_provider", "tts_base_url", ("http",)),
            ("video", "video_provider", "video_base_url", ("http",)),
        ):
            mode = str(getattr(settings, mode_attr, "mock"))
            base_url = str(getattr(settings, url_attr, ""))
            is_remote = mode in remote_modes
            placeholder = is_placeholder_endpoint(base_url) if is_remote else False
            configured = is_remote and not placeholder
            if is_remote:
                remote_count += 1
            if configured:
                configured_count += 1
            providers.append(
                {
                    "provider": name,
                    "mode": mode,
                    "base_url": base_url,
                    "is_remote_mode": is_remote,
                    "endpoint_configured": configured,
                    "ready": configured,
                    "next_step": self._next_step_for_provider(name, mode, placeholder),
                }
            )

        steps = [
            "Copy .env.example → .env on your deploy machine",
            "Set LLM_PROVIDER=openai_compatible + LLM_BASE_URL + LLM_API_KEY",
            "Set TTS_PROVIDER=http + TTS_BASE_URL",
            "Set VIDEO_PROVIDER=http + VIDEO_BASE_URL",
            "Restart server · GET /api/v1/providers/status",
            "POST /api/v1/providers/forge/smoke · make verify-forge",
            "Connect in UI · Send — real pipeline performs",
        ]

        return {
            "lane_id": "real_providers",
            "lane_title": "Real Provider Live",
            "providers": providers,
            "remote_providers": remote_count,
            "configured_providers": configured_count,
            "all_real_ready": configured_count == 3,
            "provider_gate_enabled": bool(getattr(settings, "provider_gate_enabled", False)),
            "env_checklist": list(_RUNPOD_ENV_CHECKLIST),
            "activation_steps": steps,
            "forge_status_url": "/api/v1/providers/status",
            "forge_smoke_url": "/api/v1/providers/forge/smoke",
        }

    @staticmethod
    def _next_step_for_provider(name: str, mode: str, placeholder: bool) -> str:
        if name == "llm" and mode != "openai_compatible":
            return "Set LLM_PROVIDER=openai_compatible in .env"
        if name == "tts" and mode != "http":
            return "Set TTS_PROVIDER=http in .env"
        if name == "video" and mode != "http":
            return "Set VIDEO_PROVIDER=http in .env"
        if placeholder:
            return f"Replace {name.upper()}_BASE_URL placeholder with real RunPod URL"
        return "Run POST /api/v1/providers/forge/smoke"

    def snapshot(self, *, deployment_phase: int, app_version: str, settings: Any) -> dict[str, object]:
        active = self.get_active_lane()
        real = self.build_real_provider_readiness(settings=settings)
        return {
            "deployment_phase": deployment_phase,
            "app_version": app_version,
            "empire_version": "1.0.0",
            "innovation_mode": True,
            "active_lane_id": active.get("id") if active else "real_providers",
            "active_lane_title": active.get("title") if active else "Real Provider Live",
            "lanes_total": len(self.list_lanes()),
            "real_providers_ready": real["all_real_ready"],
            "configured_providers": real["configured_providers"],
            "schema_path": self._schema_path,
        }