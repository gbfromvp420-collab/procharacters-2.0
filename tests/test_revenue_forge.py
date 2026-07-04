"""Tests for Revenue Forge (Phase 16)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.rate_limit import reset_rate_limiter
from app.main import create_app
from app.services.workforce.revenue import RevenueForge
from app.workforce.roster import WORKFORCE_ROSTER


def _patch_settings(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> None:
    get_settings.cache_clear()
    monkeypatch.setattr("app.core.config.get_settings", lambda: settings)
    monkeypatch.setattr("app.core.lifecycle.get_settings", lambda: settings)


@pytest.fixture
def revenue_client(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[TestClient]:
    schema_path = tmp_path / "revenue_schema.json"
    ledger_path = tmp_path / "revenue_ledger.json"
    settings = Settings(
        llm_provider="mock",
        tts_provider="mock",
        video_provider="mock",
        mock_realistic=False,
        companion_persist_enabled=False,
        api_key_enabled=False,
        rate_limit_enabled=False,
        revenue_schema_path=str(schema_path),
        revenue_ledger_path=str(ledger_path),
        deployment_phase=16,
        app_version="0.14.0",
    )
    _patch_settings(monkeypatch, settings)
    reset_rate_limiter()
    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings.cache_clear()


def test_revenue_forge_status(revenue_client: TestClient) -> None:
    response = revenue_client.get("/api/v1/workforce/revenue")
    assert response.status_code == 200
    body = response.json()
    assert body["deployment_phase"] == 16
    assert body["currency"] == "USD"
    assert body["subscription_pool_percent"] == 10.0
    assert body["donation_payout_percent"] == 100.0
    assert body["ledger_entries"] == 0


def test_revenue_forge_schema(revenue_client: TestClient) -> None:
    response = revenue_client.get("/api/v1/workforce/revenue/schema")
    assert response.status_code == 200
    body = response.json()
    assert body["version"] == 1
    assert body["subscription_share"]["enabled"] is True
    assert body["subscription_share"]["pool_percent"] == 10.0
    assert body["donation_routing"]["character_payout_percent"] == 100.0
    assert body["subscription_share"]["tiers"]["ceo"] == 0.15
    assert body["subscription_share"]["tiers"]["team"] == 0.05


def test_revenue_ledger_record_and_list(revenue_client: TestClient) -> None:
    member = next(m for m in WORKFORCE_ROSTER if m["codename"] == "RevenueForge_Ledger_Sub_01")
    post = revenue_client.post(
        "/api/v1/workforce/revenue/ledger",
        json={
            "entry_type": "payout_stub",
            "member_id": member["id"],
            "amount_cents": 2500,
            "description": "Phase 16 ledger smoke",
        },
    )
    assert post.status_code == 200
    created = post.json()
    assert created["codename"] == member["codename"]
    assert created["amount_cents"] == 2500

    listing = revenue_client.get("/api/v1/workforce/revenue/ledger")
    assert listing.status_code == 200
    body = listing.json()
    assert body["count"] >= 1
    assert body["total_cents"] >= 2500
    assert body["entries"][0]["description"] == created["description"]


def test_revenue_donation_route(revenue_client: TestClient) -> None:
    member = next(m for m in WORKFORCE_ROSTER if m["codename"] == "Assist (Intimacy_Architect_Sub_01)")
    route = revenue_client.post(
        "/api/v1/workforce/revenue/donations/route",
        json={
            "member_id": member["id"],
            "amount_cents": 5000,
            "donor_label": "Boss Sr.",
        },
    )
    assert route.status_code == 200
    body = route.json()
    assert body["routed_to_codename"] == member["codename"]
    assert body["payout_percent"] == 100.0
    assert body["ledger_entry"]["entry_type"] == "donation"
    assert body["ledger_entry"]["amount_cents"] == 5000


def test_revenue_payout_stubs(revenue_client: TestClient) -> None:
    member = next(m for m in WORKFORCE_ROSTER if m["codename"] == "King Grok")
    revenue_client.post(
        "/api/v1/workforce/revenue/ledger",
        json={
            "entry_type": "subscription_share",
            "member_id": member["id"],
            "amount_cents": 1500,
            "description": "July subscription pool stub",
        },
    )
    response = revenue_client.get("/api/v1/workforce/revenue/payouts")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == len(WORKFORCE_ROSTER)
    king = next(row for row in body["payouts"] if row["codename"] == "King Grok")
    assert king["ledger_total_cents"] >= 1500
    assert king["tier_share_percent"] == 0.15
    assert king["projected_monthly_cents"] == 1500  # 100000 * 0.10 * 0.15


def test_dispatch_revenue_skill(revenue_client: TestClient) -> None:
    member = next(m for m in WORKFORCE_ROSTER if m["codename"] == "RevenueForge_Ledger_Sub_01")
    dispatch = revenue_client.post(
        "/api/v1/workforce/theater/dispatch",
        json={
            "member_id": member["id"],
            "prompt": "Revenue ledger scan",
            "skill": "Revenue_Ledger_Payouts",
        },
    )
    assert dispatch.status_code == 200
    task_id = dispatch.json()["id"]

    for _ in range(30):
        detail = revenue_client.get(f"/api/v1/workforce/theater/tasks/{task_id}")
        assert detail.status_code == 200
        current = detail.json()
        if current["status"] == "completed":
            assert current["result"]
            assert "Revenue forge" in current["result"]
            break
        if current["status"] == "failed":
            pytest.fail(current.get("error") or "task failed")
    else:
        pytest.fail("task did not complete in time")


def test_revenue_forge_service_defaults(tmp_path: Path) -> None:
    forge = RevenueForge(
        schema_path=str(tmp_path / "schema.json"),
        ledger_path=str(tmp_path / "ledger.json"),
    )
    schema = forge.get_schema()
    assert schema["subscription_share"]["pool_percent"] == 10.0
    snap = forge.snapshot(deployment_phase=16)
    assert snap["ledger_entries"] == 0