"""Innovation lanes — post-v1.0 product roadmap (Real, Soul, $, Live)."""

from __future__ import annotations

import copy
import json
import logging
from pathlib import Path
from typing import Any

from app.services.providers.contracts import is_placeholder_endpoint
from app.services.providers.local_stubs import (
    detect_stage1_source,
    runpod_howto,
    stage1_blocker,
    stage1_status,
)

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
            "summary": (
                "HTTP LLM → TTS → MuseTalk contracts — local stubs unblock Stage 1; "
                "RunPod Connect URLs go live."
            ),
            "status": "in_progress",
        },
        {
            "id": "companion_soul",
            "rank": 2,
            "label": "Soul",
            "title": "Companion Depth",
            "summary": "Named memories, soul stages, check-in — Assist's platinum lane.",
            "status": "in_progress",
        },
        {
            "id": "characters_revenue",
            "rank": 3,
            "label": "$",
            "title": "Characters + Revenue",
            "summary": "NSM pipeline spec, earnings rollup, first dollar — residuals + donations + live.",
            "status": "in_progress",
        },
        {
            "id": "live_launch",
            "rank": 4,
            "label": "Live",
            "title": "Live Launch",
            "summary": "Assist headline night, public board, stage-door lounge comments.",
            "status": "in_progress",
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
        return copy.deepcopy(_DEFAULT_SCHEMA)

    def _save_schema(self) -> None:
        path = Path(self._schema_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self._schema, indent=2), encoding="utf-8")

    def set_lane_status(self, lane_id: str, status: str) -> None:
        lanes = self._schema.setdefault("lanes", [])
        if not isinstance(lanes, list):
            return
        for lane in lanes:
            if isinstance(lane, dict) and lane.get("id") == lane_id:
                lane["status"] = status
                break
        self._save_schema()

    def set_active_lane(self, lane_id: str) -> dict[str, Any] | None:
        known = {lane.get("id") for lane in self.list_lanes()}
        if lane_id not in known:
            return None
        self._schema["active_lane"] = lane_id
        self._save_schema()
        return self.get_active_lane()

    def next_lane_id(self, current_id: str) -> str | None:
        ordered = self.list_lanes()
        ids = [str(lane.get("id")) for lane in ordered]
        try:
            index = ids.index(current_id)
        except ValueError:
            return ids[0] if ids else None
        if index + 1 >= len(ids):
            return None
        return ids[index + 1]

    def sync_real_lane(self, *, settings: Any, wired: bool = False) -> str:
        real = self.build_real_provider_readiness(settings=settings, wired=wired)
        status = str(real["stage1_status"])
        self.set_lane_status("real_providers", status)
        return status

    def get_schema(self) -> dict[str, Any]:
        return copy.deepcopy(self._schema)

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

    def build_real_provider_readiness(
        self, *, settings: Any, wired: bool = False
    ) -> dict[str, Any]:
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

        ready = configured_count == 3
        source = detect_stage1_source(settings=settings, wired=wired and ready)
        status = stage1_status(ready=ready, source=source)
        steps = [
            "POST /api/v1/workforce/innovation/wire/local — finish Stage 1 without pods",
            "Or paste RunPod Connect URLs into Innovation · Wire",
            "POST /api/v1/providers/forge/smoke",
            "POST /api/v1/workforce/innovation/advance — move active lane to Soul",
            "When pods exist: swap local stub URLs for RunPod proxies (no restart)",
        ]

        return {
            "lane_id": "real_providers",
            "lane_title": "Real Provider Live",
            "providers": providers,
            "remote_providers": remote_count,
            "configured_providers": configured_count,
            "all_real_ready": ready,
            "provider_gate_enabled": bool(getattr(settings, "provider_gate_enabled", False)),
            "env_checklist": list(_RUNPOD_ENV_CHECKLIST),
            "activation_steps": steps,
            "forge_status_url": "/api/v1/providers/status",
            "forge_smoke_url": "/api/v1/providers/forge/smoke",
            "stage1_status": status,
            "stage1_source": source,
            "stage1_blocker": stage1_blocker(
                ready=ready, source=source, configured=configured_count
            ),
            "runpod_howto": runpod_howto(),
            "runpod_console": "https://www.runpod.io/console/pods",
        }

    @staticmethod
    def _next_step_for_provider(name: str, mode: str, placeholder: bool) -> str:
        if name == "llm" and mode != "openai_compatible":
            return "POST /workforce/innovation/wire/local or set LLM_PROVIDER=openai_compatible"
        if name == "tts" and mode != "http":
            return "POST /workforce/innovation/wire/local or set TTS_PROVIDER=http"
        if name == "video" and mode != "http":
            return "POST /workforce/innovation/wire/local or set VIDEO_PROVIDER=http"
        if placeholder:
            return (
                f"Replace {name.upper()}_BASE_URL with local stubs "
                "(/api/v1/providers/local) or a RunPod Connect URL"
            )
        return "Run POST /api/v1/providers/forge/smoke"

    def snapshot(self, *, deployment_phase: int, app_version: str, settings: Any) -> dict[str, object]:
        active = self.get_active_lane()
        real = self.build_real_provider_readiness(settings=settings)
        lane_status = {lane.get("id"): lane.get("status", "in_progress") for lane in self.list_lanes()}
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
            "soul_lane_status": str(lane_status.get("companion_soul", "in_progress")),
            "money_lane_status": str(lane_status.get("characters_revenue", "in_progress")),
            "live_lane_status": str(lane_status.get("live_launch", "in_progress")),
            "live_activate": True,
            "schema_path": self._schema_path,
            "stage1_status": real["stage1_status"],
            "stage1_source": real["stage1_source"],
            "stage1_blocker": real["stage1_blocker"],
        }