"""KGC fleet backup and restore helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.companion.store import SessionCompanionStore
from app.services.kgc.audit import AuditLog
from app.services.kgc.policies import KGCPolicies


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_fleet_backup(
    companion_store: SessionCompanionStore,
    policies: KGCPolicies,
    audit_log: AuditLog,
    *,
    audit_tail_limit: int = 50,
) -> dict[str, Any]:
    return {
        "version": "1",
        "exported_at": _utc_now_iso(),
        "companion_sessions": companion_store.export_all_sessions(),
        "policies": policies.snapshot(),
        "audit_tail": audit_log.tail(limit=audit_tail_limit),
    }


def restore_fleet_backup(
    companion_store: SessionCompanionStore,
    policies: KGCPolicies,
    payload: dict[str, Any],
) -> dict[str, int]:
    sessions_raw = payload.get("companion_sessions", {})
    if not isinstance(sessions_raw, dict):
        sessions_raw = {}

    merged = companion_store.merge_sessions(sessions_raw)

    policies_raw = payload.get("policies")
    if isinstance(policies_raw, dict):
        policies.apply_snapshot(policies_raw)

    return {
        "sessions_merged": merged,
        "sessions_total": len(companion_store.list_session_ids()),
    }