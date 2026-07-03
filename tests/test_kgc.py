"""Tests for KGC Executive Command Layer (Phase 7 Lane 1)."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.models.llm import ChatMessage
from app.services.companion.store import SessionCompanionStore
from app.services.kgc.command import build_dashboard, build_fleet
from app.services.webrtc.session_manager import WebRTCSessionManager
from app.workforce.roster import WORKFORCE_ROSTER


@pytest.fixture
def api_client() -> TestClient:
    with TestClient(create_app()) as client:
        yield client


def test_build_fleet_merges_webrtc_and_companion() -> None:
    settings = Settings(companion_persist_enabled=False)
    companion_store = SessionCompanionStore(settings=settings)
    session_manager = WebRTCSessionManager(settings=settings, companion_store=companion_store)

    webrtc_session = session_manager.create_session()
    companion_only = "companion-only-session"
    companion_store.append_turn(
        companion_only,
        ChatMessage(role="user", content="Hi"),
        ChatMessage(role="assistant", content="Hello"),
    )

    fleet = build_fleet(companion_store, session_manager)
    by_id = {entry["session_id"]: entry for entry in fleet}

    assert len(fleet) == 2
    assert webrtc_session.session_id in by_id
    assert companion_only in by_id

    webrtc_entry = by_id[webrtc_session.session_id]
    assert webrtc_entry["webrtc_active"] is True
    assert webrtc_entry["companion_active"] is False
    assert webrtc_entry["connection_state"] == "new"

    companion_entry = by_id[companion_only]
    assert companion_entry["webrtc_active"] is False
    assert companion_entry["companion_active"] is True
    assert companion_entry["turn_count"] == 1
    assert companion_entry["bond_score"] == 3


def test_kgc_dashboard_api(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/kgc/dashboard")
    assert response.status_code == 200
    body = response.json()

    assert body["app_version"] == "0.8.0"
    assert body["kgc_status"] == "operational"
    assert body["uptime_seconds"] >= 0
    assert body["active_webrtc_sessions"] >= 0
    assert isinstance(body["webrtc_sessions"], list)
    assert body["companion_sessions_count"] >= 0
    assert body["companion_total_turns"] >= 0
    assert body["companion_avg_bond_score"] >= 0
    assert body["workforce_count"] == len(WORKFORCE_ROSTER)
    assert body["workforce_total_gold_lb"] == round(
        sum(member["award_lb_gold"] for member in WORKFORCE_ROSTER),
        2,
    )
    assert "providers_summary" in body
    assert "llm" in body["providers_summary"]
    assert "metrics_snapshot" in body
    assert "perform_requests" in body["metrics_snapshot"]


def test_kgc_fleet_api(api_client: TestClient) -> None:
    created = api_client.post("/api/v1/webrtc/session")
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    response = api_client.get("/api/v1/kgc/fleet")
    assert response.status_code == 200
    body = response.json()

    assert "fleet" in body
    assert "count" in body
    assert body["count"] == len(body["fleet"])

    entry = next((item for item in body["fleet"] if item["session_id"] == session_id), None)
    assert entry is not None
    assert entry["webrtc_active"] is True
    assert entry["connection_state"] == "new"


def test_kgc_fleet_prune_api(api_client: TestClient) -> None:
    store: SessionCompanionStore = api_client.app.state.companion_store
    settings: Settings = api_client.app.state.settings

    fresh_sid = "kgc-fresh-session"
    stale_sid = "kgc-stale-session"

    store.get_or_create(fresh_sid)
    stale_state = store.get_or_create(stale_sid)
    stale_state.last_active_at = (
        datetime.now(timezone.utc) - timedelta(hours=settings.companion_session_ttl_hours + 1)
    ).isoformat()
    store.save_all()

    response = api_client.post("/api/v1/kgc/fleet/prune")
    assert response.status_code == 200
    body = response.json()

    assert body["ttl_hours"] == settings.companion_session_ttl_hours
    assert body["pruned"] >= 1
    assert fresh_sid in store.list_session_ids()
    assert stale_sid not in store.list_session_ids()


@pytest.mark.asyncio
async def test_build_dashboard_service(api_client: TestClient) -> None:
    request = type("Req", (), {"app": api_client.app})()
    dashboard = await build_dashboard(request)

    assert dashboard["app_version"] == "0.8.0"
    assert dashboard["kgc_status"] == "operational"
    assert dashboard["workforce_count"] == len(WORKFORCE_ROSTER)
    assert "metrics_snapshot" in dashboard
    assert "providers_summary" in dashboard