"""KGC Executive Command Layer — dashboard and fleet aggregation."""

from __future__ import annotations

import time
from typing import Any

from fastapi import Request

from app.services.companion.store import SessionCompanionStore
from app.services.webrtc.session_manager import WebRTCSessionManager
from app.workforce.roster import WORKFORCE_ROSTER


def _companion_stats(companion_store: SessionCompanionStore) -> tuple[int, int, float]:
    """Return (session_count, total_turns, avg_bond_score)."""
    sessions = companion_store.list_persisted_sessions()
    if not sessions:
        return 0, 0, 0.0
    total_turns = sum(int(s.get("turn_count", 0)) for s in sessions)
    bond_scores = [int(s.get("bond_score", 0)) for s in sessions]
    avg_bond = sum(bond_scores) / len(bond_scores) if bond_scores else 0.0
    return len(sessions), total_turns, round(avg_bond, 2)


def _workforce_stats() -> tuple[int, float]:
    """Return (member_count, total_gold_lb)."""
    total_gold = sum(member["award_lb_gold"] for member in WORKFORCE_ROSTER)
    return len(WORKFORCE_ROSTER), round(total_gold, 2)


def build_fleet(
    companion_store: SessionCompanionStore,
    session_manager: WebRTCSessionManager,
) -> list[dict[str, Any]]:
    """Merge active WebRTC sessions and persisted companion sessions by session_id."""
    webrtc_by_id = {
        item["session_id"]: item for item in session_manager.list_sessions_with_details()
    }
    companion_by_id = {item["id"]: item for item in companion_store.list_persisted_sessions()}

    fleet: list[dict[str, Any]] = []
    for session_id in sorted(set(webrtc_by_id) | set(companion_by_id)):
        webrtc = webrtc_by_id.get(session_id)
        companion = companion_by_id.get(session_id)
        entry: dict[str, Any] = {
            "session_id": session_id,
            "webrtc_active": webrtc is not None,
            "companion_active": companion is not None,
        }
        if webrtc is not None:
            entry["connection_state"] = webrtc.get("connection_state")
            entry["ice_connection_state"] = webrtc.get("ice_connection_state")
            entry["ice_gathering_state"] = webrtc.get("ice_gathering_state")
            entry["webrtc_created_at"] = webrtc.get("created_at")
        if companion is not None:
            entry["turn_count"] = companion.get("turn_count", 0)
            entry["bond_score"] = companion.get("bond_score", 0)
            entry["avatar_id"] = companion.get("avatar_id")
            entry["last_active_at"] = companion.get("last_active_at")
        fleet.append(entry)
    return fleet


async def build_dashboard(request: Request) -> dict[str, Any]:
    """Aggregate executive command dashboard from app state and live probes."""
    settings = request.app.state.settings
    session_manager: WebRTCSessionManager = request.app.state.session_manager
    companion_store: SessionCompanionStore = request.app.state.companion_store
    metrics = request.app.state.metrics
    provider_probe = request.app.state.provider_probe
    started_at: float = request.app.state.started_at_monotonic

    webrtc_sessions = session_manager.list_sessions_with_details()
    companion_count, total_turns, avg_bond = _companion_stats(companion_store)
    workforce_count, total_gold_lb = _workforce_stats()
    providers_summary = await provider_probe.get_providers_summary(timeout_seconds=2.0)

    return {
        "app_version": settings.app_version,
        "uptime_seconds": round(time.monotonic() - started_at, 3),
        "metrics_snapshot": metrics.snapshot(),
        "active_webrtc_sessions": session_manager.active_session_count,
        "webrtc_sessions": webrtc_sessions,
        "companion_sessions_count": companion_count,
        "companion_total_turns": total_turns,
        "companion_avg_bond_score": avg_bond,
        "providers_summary": providers_summary,
        "workforce_count": workforce_count,
        "workforce_total_gold_lb": total_gold_lb,
        "kgc_status": "operational",
    }