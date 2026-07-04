"""Tests for Live Stage (Phase 18)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.rate_limit import reset_rate_limiter
from app.main import create_app
from app.services.workforce.live_stage import LiveStage
from app.workforce.roster import WORKFORCE_ROSTER


def _patch_settings(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> None:
    get_settings.cache_clear()
    monkeypatch.setattr("app.core.config.get_settings", lambda: settings)
    monkeypatch.setattr("app.core.lifecycle.get_settings", lambda: settings)


@pytest.fixture
def live_client(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[TestClient]:
    settings = Settings(
        llm_provider="mock",
        tts_provider="mock",
        video_provider="mock",
        mock_realistic=False,
        companion_persist_enabled=False,
        api_key_enabled=False,
        rate_limit_enabled=False,
        revenue_schema_path=str(tmp_path / "revenue_schema.json"),
        revenue_ledger_path=str(tmp_path / "revenue_ledger.json"),
        live_stage_schema_path=str(tmp_path / "live_stage_schema.json"),
        live_stage_sessions_path=str(tmp_path / "live_stage_sessions.json"),
        live_stage_billing_path=str(tmp_path / "live_stage_billing.json"),
        deployment_phase=18,
        app_version="0.16.0",
    )
    _patch_settings(monkeypatch, settings)
    reset_rate_limiter()
    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings.cache_clear()


def test_live_stage_status(live_client: TestClient) -> None:
    response = live_client.get("/api/v1/workforce/live")
    assert response.status_code == 200
    body = response.json()
    assert body["deployment_phase"] == 18
    assert body["cam_enabled"] is True
    assert body["donation_payout_percent"] == 100.0
    assert body["host_share_percent"] == 70.0


def test_live_stage_schema(live_client: TestClient) -> None:
    response = live_client.get("/api/v1/workforce/live/schema")
    assert response.status_code == 200
    body = response.json()
    assert body["version"] == 1
    assert body["cam_chat"]["min_donation_cents"] == 100
    assert body["ticketed_shows"]["default_ticket_price_cents"] == 2500


def test_cam_session_donation_and_end(live_client: TestClient) -> None:
    member = next(m for m in WORKFORCE_ROSTER if m["codename"] == "LiveStage_Cam_Sub_01")
    start = live_client.post(
        "/api/v1/workforce/live/cam/start",
        json={"member_id": member["id"], "title": "Phase 18 cam smoke"},
    )
    assert start.status_code == 200
    session = start.json()
    assert session["status"] == "live"
    session_id = session["id"]

    donation = live_client.post(
        "/api/v1/workforce/live/billing/donation",
        json={
            "live_session_id": session_id,
            "amount_cents": 1500,
            "donor_label": "Boss Sr.",
        },
    )
    assert donation.status_code == 200
    body = donation.json()
    assert body["payout_percent"] == 100.0
    assert body["billing_entry"]["host_payout_cents"] == 1500
    assert body["revenue_routed"] is True

    end = live_client.post(f"/api/v1/workforce/live/sessions/{session_id}/end")
    assert end.status_code == 200
    assert end.json()["status"] == "ended"


def test_ticketed_show_schedule_start_ticket(live_client: TestClient) -> None:
    member = next(m for m in WORKFORCE_ROSTER if m["codename"] == "Assist (Intimacy_Architect_Sub_01)")
    scheduled_at = (datetime.now(UTC) + timedelta(days=2)).isoformat()
    schedule = live_client.post(
        "/api/v1/workforce/live/shows/schedule",
        json={
            "member_id": member["id"],
            "title": "Private ticketed show",
            "scheduled_at": scheduled_at,
            "ticket_price_cents": 3000,
        },
    )
    assert schedule.status_code == 200
    show = schedule.json()
    assert show["status"] == "scheduled"
    show_id = show["id"]

    ticket = live_client.post(
        "/api/v1/workforce/live/billing/ticket",
        json={"live_session_id": show_id, "buyer_label": "fan_01"},
    )
    assert ticket.status_code == 200
    assert ticket.json()["host_payout_cents"] == 2100  # 70% of 3000

    start = live_client.post(f"/api/v1/workforce/live/shows/{show_id}/start")
    assert start.status_code == 200
    assert start.json()["status"] == "live"


def test_dispatch_live_stage_skill(live_client: TestClient) -> None:
    member = next(m for m in WORKFORCE_ROSTER if m["codename"] == "LiveStage_Cam_Sub_01")
    dispatch = live_client.post(
        "/api/v1/workforce/theater/dispatch",
        json={
            "member_id": member["id"],
            "prompt": "Live stage scan",
            "skill": "Live_Stage_CamChat",
        },
    )
    assert dispatch.status_code == 200
    task_id = dispatch.json()["id"]

    for _ in range(30):
        detail = live_client.get(f"/api/v1/workforce/theater/tasks/{task_id}")
        assert detail.status_code == 200
        current = detail.json()
        if current["status"] == "completed":
            assert current["result"]
            assert "Live stage" in current["result"]
            break
        if current["status"] == "failed":
            pytest.fail(current.get("error") or "task failed")
    else:
        pytest.fail("task did not complete in time")


def test_live_stage_service_defaults(tmp_path: Path) -> None:
    stage = LiveStage(
        schema_path=str(tmp_path / "schema.json"),
        sessions_path=str(tmp_path / "sessions.json"),
        billing_path=str(tmp_path / "billing.json"),
    )
    schema = stage.get_schema()
    assert schema["cam_chat"]["donation_payout_percent"] == 100.0
    snap = stage.snapshot(deployment_phase=18)
    assert snap["sessions_total"] == 0