"""Production readiness checks for orchestrator probes."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.services.providers.gate import check_providers_ready

if TYPE_CHECKING:
    from fastapi import Request

    from app.core.config import Settings


def _path_writable(path_str: str) -> tuple[bool, str]:
    path = Path(path_str)
    parent = path.parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
        probe = parent / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True, str(path)
    except OSError as exc:
        return False, str(exc)


async def evaluate_readiness(request: Request) -> tuple[bool, dict[str, Any]]:
    """Return (ready, checks) for load balancers and docker healthchecks."""
    settings: Settings = request.app.state.settings
    checks: dict[str, Any] = {}
    ready = True

    if settings.companion_persist_enabled:
        ok, detail = _path_writable(settings.companion_persist_path)
        checks["companion_persist"] = {
            "ok": ok,
            "path": settings.companion_persist_path,
            **({"error": detail} if not ok else {}),
        }
        ready = ready and ok
    else:
        checks["companion_persist"] = {"ok": True, "skipped": True}

    ok_policies, policies_detail = _path_writable(settings.kgc_policies_path)
    checks["kgc_policies"] = {
        "ok": ok_policies,
        "path": settings.kgc_policies_path,
        **({"error": policies_detail} if not ok_policies else {}),
    }
    ready = ready and ok_policies

    providers_ok, providers_msg = await check_providers_ready(
        request.app, ["llm", "tts", "video"]
    )
    checks["providers"] = {
        "ok": providers_ok,
        "message": providers_msg or "ok",
        "gate_enabled": settings.provider_gate_enabled,
        "allow_degraded": settings.provider_gate_allow_degraded,
    }
    ready = ready and providers_ok

    started_at = getattr(request.app.state, "started_at_monotonic", None)
    if started_at is not None:
        import time

        checks["uptime_seconds"] = round(time.monotonic() - started_at, 2)

    return ready, checks