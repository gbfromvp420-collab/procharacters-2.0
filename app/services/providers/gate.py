"""Gate chat perform/speak until configured remote providers pass health probes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.models.providers import ProviderHealthStatus, ProviderName

if TYPE_CHECKING:
    from fastapi import FastAPI

_REMOTE_MODES: dict[ProviderName, frozenset[str]] = {
    "llm": frozenset({"openai_compatible"}),
    "tts": frozenset({"http"}),
    "video": frozenset({"http"}),
}

_PROBE_METHODS = {
    "llm": "probe_llm",
    "tts": "probe_tts",
    "video": "probe_video",
}


def _provider_mode(settings: object, name: ProviderName) -> str:
    return getattr(settings, f"{name}_provider")


def _status_blocks(
    status: ProviderHealthStatus,
    *,
    allow_degraded: bool,
) -> bool:
    if status == "unreachable":
        return True
    if status == "degraded" and not allow_degraded:
        return True
    return False


async def check_providers_ready(app: FastAPI, required: list[str]) -> tuple[bool, str]:
    """Return (ok, message). Blocks when gate is on and a required remote provider fails probe."""
    settings = app.state.settings
    if not settings.provider_gate_enabled:
        return True, ""

    probe = app.state.provider_probe
    allow_degraded = settings.provider_gate_allow_degraded

    for raw_name in required:
        name = raw_name.lower().strip()
        if name not in _PROBE_METHODS:
            continue

        mode = _provider_mode(settings, name)  # type: ignore[arg-type]
        if mode == "mock" or mode not in _REMOTE_MODES[name]:  # type: ignore[index]
            continue

        probe_fn = getattr(probe, _PROBE_METHODS[name])
        result = await probe_fn()
        if _status_blocks(result.status, allow_degraded=allow_degraded):
            return False, f"{name} provider {result.status}: {result.message}"

    return True, ""