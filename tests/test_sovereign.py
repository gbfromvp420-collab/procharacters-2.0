"""Tests for KGC Sovereign layer (Phase 8 Lane 2)."""

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.models.llm import ChatMessage
from app.services.companion.store import SessionCompanionStore
from app.services.kgc.audit import AuditLog, log_action
from app.services.kgc.backup import build_fleet_backup, restore_fleet_backup
from app.services.kgc.policies import KGCPolicies
from app.services.observability.prometheus import format_prometheus_metrics
from app.services.observability.metrics import MetricsCollector


@pytest.fixture
def api_client() -> TestClient:
    with TestClient(create_app()) as client:
        yield client


def test_audit_ring_buffer_max_entries() -> None:
    audit = AuditLog(max_entries=200)
    for index in range(250):
        audit.log_action("test.action", f"entry={index}")

    entries = audit.get_entries(limit=200)
    assert len(entries) == 200
    assert entries[0].detail == "entry=249"
    assert entries[-1].detail == "entry=50"


def test_audit_log_action_module_helper() -> None:
    entry = log_action("unit.test", "detail=hello", result="ok")
    assert entry.action == "unit.test"
    assert entry.actor == "ceo"
    assert entry.result == "ok"


def test_kgc_policies_persist_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "kgc_policies.json"
    policies = KGCPolicies(path=str(path))
    updated = policies.update(
        default_relationship_mode="romantic",
        default_system_prompt="CEO default prompt.",
        auto_prune_enabled=False,
    )
    assert updated["default_relationship_mode"] == "romantic"
    assert path.exists()

    reloaded = KGCPolicies(path=str(path))
    snapshot = reloaded.snapshot()
    assert snapshot["default_relationship_mode"] == "romantic"
    assert snapshot["default_system_prompt"] == "CEO default prompt."
    assert snapshot["auto_prune_enabled"] is False


def test_new_sessions_inherit_policy_defaults(tmp_path: Path) -> None:
    policies_path = tmp_path / "kgc_policies.json"
    policies = KGCPolicies(path=str(policies_path))
    policies.update(
        default_relationship_mode="deep",
        default_system_prompt="Inherited prompt.",
    )

    settings = Settings(companion_persist_enabled=False)
    store = SessionCompanionStore(settings=settings, kgc_policies=policies)
    cfg = store.get_config("policy-session")

    assert cfg["relationship_mode"] == "deep"
    assert cfg["system_prompt"] == "Inherited prompt."


def test_kgc_policies_api(api_client: TestClient) -> None:
    get_resp = api_client.get("/api/v1/kgc/policies")
    assert get_resp.status_code == 200
    body = get_resp.json()
    assert "default_relationship_mode" in body
    assert "default_system_prompt" in body
    assert "auto_prune_enabled" in body

    patch_resp = api_client.patch(
        "/api/v1/kgc/policies",
        json={
            "default_relationship_mode": "friendly",
            "default_system_prompt": "Fleet default.",
            "auto_prune_enabled": True,
        },
    )
    assert patch_resp.status_code == 200
    patched = patch_resp.json()
    assert patched["default_relationship_mode"] == "friendly"
    assert patched["default_system_prompt"] == "Fleet default."


def test_fleet_clone_import_and_audit(api_client: TestClient) -> None:
    store: SessionCompanionStore = api_client.app.state.companion_store
    source_id = f"sovereign-source-{uuid.uuid4().hex[:8]}"
    clone_id = f"sovereign-clone-{uuid.uuid4().hex[:8]}"
    import_id = f"sovereign-imported-{uuid.uuid4().hex[:8]}"
    store.append_turn(
        source_id,
        ChatMessage(role="user", content="Hello"),
        ChatMessage(role="assistant", content="Hi"),
    )
    store.set_config(source_id, relationship_mode="friendly")

    clone_resp = api_client.post(
        "/api/v1/kgc/fleet/clone",
        json={"source_session_id": source_id, "target_session_id": clone_id},
    )
    assert clone_resp.status_code == 200
    assert clone_resp.json()["target_session_id"] == clone_id

    import_resp = api_client.post(
        "/api/v1/kgc/fleet/import",
        json={
            "session_id": import_id,
            "data": {
                "avatar_id": "professional",
                "voice": "warm",
                "system_prompt": "Imported.",
                "relationship_mode": "deep",
                "bond_score": 12,
                "messages": [
                    {"role": "user", "content": "Import me"},
                    {"role": "assistant", "content": "Done"},
                ],
            },
        },
    )
    assert import_resp.status_code == 200
    imported_cfg = store.get_config(import_id)
    assert imported_cfg["avatar_id"] == "professional"
    assert imported_cfg["turn_count"] == 1

    audit_resp = api_client.get("/api/v1/kgc/audit?limit=10")
    assert audit_resp.status_code == 200
    actions = {entry["action"] for entry in audit_resp.json()["entries"]}
    assert "fleet.clone" in actions
    assert "fleet.import" in actions
    assert "policies.update" in actions


def test_fleet_backup_and_restore_merge(api_client: TestClient) -> None:
    store: SessionCompanionStore = api_client.app.state.companion_store
    policies: KGCPolicies = api_client.app.state.kgc_policies

    store.get_or_create("backup-a")
    store.set_config("backup-a", relationship_mode="friendly")
    policies.update(default_relationship_mode="romantic", default_system_prompt="Backup prompt.")

    backup_resp = api_client.get("/api/v1/kgc/fleet/backup")
    assert backup_resp.status_code == 200
    assert "attachment" in backup_resp.headers.get("Content-Disposition", "")
    backup = backup_resp.json()
    assert backup["version"] == "1"
    assert "backup-a" in backup["companion_sessions"]
    assert backup["policies"]["default_relationship_mode"] == "romantic"
    assert isinstance(backup["audit_tail"], list)

    store.remove("backup-a")
    assert "backup-a" not in store.list_session_ids()

    restore_resp = api_client.post("/api/v1/kgc/fleet/restore", json=backup)
    assert restore_resp.status_code == 200
    restored = restore_resp.json()
    assert restored["sessions_merged"] >= 1
    assert "backup-a" in store.list_session_ids()
    assert policies.snapshot()["default_relationship_mode"] == "romantic"


def test_fleet_prune_logs_audit(api_client: TestClient) -> None:
    store: SessionCompanionStore = api_client.app.state.companion_store
    settings: Settings = api_client.app.state.settings

    fresh_sid = "sovereign-fresh"
    stale_sid = "sovereign-stale"
    store.get_or_create(fresh_sid)
    stale_state = store.get_or_create(stale_sid)
    stale_state.last_active_at = (
        datetime.now(timezone.utc) - timedelta(hours=settings.companion_session_ttl_hours + 1)
    ).isoformat()
    store.save_all()

    prune_resp = api_client.post("/api/v1/kgc/fleet/prune")
    assert prune_resp.status_code == 200
    assert prune_resp.json()["pruned"] >= 1
    assert stale_sid not in store.list_session_ids()
    assert fresh_sid in store.list_session_ids()

    audit_resp = api_client.get("/api/v1/kgc/audit?limit=20")
    assert any(entry["action"] == "fleet.prune" for entry in audit_resp.json()["entries"])


def test_prometheus_metrics_endpoint(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/metrics/prometheus")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    body = response.text
    assert "procharacters_perform_requests" in body
    assert "procharacters_uptime_seconds" in body
    assert "# TYPE procharacters_perform_requests counter" in body


def test_format_prometheus_metrics_helper() -> None:
    metrics = MetricsCollector()
    metrics.increment_perform_requests(3)
    body = format_prometheus_metrics(metrics, 12.5)
    assert "procharacters_perform_requests 3" in body
    assert "procharacters_uptime_seconds 12.5" in body


def test_backup_service_round_trip() -> None:
    settings = Settings(companion_persist_enabled=False)
    policies = KGCPolicies(path="/tmp/unused-kgc-policies-test.json")
    policies.update(default_relationship_mode="flirtatious")
    store = SessionCompanionStore(settings=settings, kgc_policies=policies)
    audit = AuditLog()
    audit.log_action("seed", "backup-test")

    store.append_turn(
        "svc-session",
        ChatMessage(role="user", content="A"),
        ChatMessage(role="assistant", content="B"),
    )

    backup = build_fleet_backup(store, policies, audit)
    store.remove("svc-session")
    result = restore_fleet_backup(store, policies, backup)

    assert result["sessions_merged"] == 1
    assert store.get_config("svc-session")["turn_count"] == 1
    assert policies.snapshot()["default_relationship_mode"] == "flirtatious"