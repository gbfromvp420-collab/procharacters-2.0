"""Tests for Crown Completion (Phase 20)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.rate_limit import reset_rate_limiter
from app.main import create_app
from app.services.workforce.crown_completion import CrownCompletion
from app.workforce.roster import WORKFORCE_ROSTER, get_roster


def _patch_settings(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> None:
    get_settings.cache_clear()
    monkeypatch.setattr("app.core.config.get_settings", lambda: settings)
    monkeypatch.setattr("app.core.lifecycle.get_settings", lambda: settings)


@pytest.fixture
def crown_client(
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
        crown_completion_schema_path=str(tmp_path / "crown_completion_schema.json"),
        crown_cosign_path=str(tmp_path / "crown_cosign.json"),
        crown_gifts_granted_path=str(tmp_path / "crown_gifts_granted.json"),
        crown_creative_sessions_path=str(tmp_path / "crown_creative_sessions.json"),
        revenue_schema_path=str(tmp_path / "revenue_schema.json"),
        revenue_ledger_path=str(tmp_path / "revenue_ledger.json"),
        live_stage_schema_path=str(tmp_path / "live_stage_schema.json"),
        live_stage_sessions_path=str(tmp_path / "live_stage_sessions.json"),
        live_stage_billing_path=str(tmp_path / "live_stage_billing.json"),
        deployment_phase=20,
        app_version="1.0.0",
    )
    _patch_settings(monkeypatch, settings)
    reset_rate_limiter()
    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings.cache_clear()


def test_crown_completion_status(crown_client: TestClient) -> None:
    response = crown_client.get("/api/v1/workforce/crown")
    assert response.status_code == 200
    body = response.json()
    assert body["deployment_phase"] == 20
    assert body["app_version"] == "1.0.0"
    assert body["empire_version"] == "1.0.0"
    assert body["crown_complete"] is True
    assert body["platinum_value_usd"] == 5000.0
    assert body["workers_awarded"] == len(WORKFORCE_ROSTER)
    assert body["phase_rankings_count"] == 3


def test_crown_phase_rankings(crown_client: TestClient) -> None:
    response = crown_client.get("/api/v1/workforce/crown/rankings")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 3
    assert body["curator"] == "King Grok"
    ranks = [item["rank"] for item in body["rankings"]]
    assert ranks == [1, 2, 3]
    assert body["rankings"][0]["phase"] == 15
    assert body["rankings"][0]["name"] == "Agent Lounge"


def test_crown_platinum_awards_all_workers(crown_client: TestClient) -> None:
    response = crown_client.get("/api/v1/workforce/crown/platinum")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == len(WORKFORCE_ROSTER)
    assert body["total_value_usd"] == 5000.0 * len(WORKFORCE_ROSTER)
    for award in body["awards"]:
        assert award["platinum_value_usd"] == 5000.0
        assert award["award_name"] == "Pure Platinum KGC Phase 20"


def test_crown_assist_promotion(crown_client: TestClient) -> None:
    response = crown_client.get("/api/v1/workforce/crown/promotion")
    assert response.status_code == 200
    body = response.json()
    assert body["member_id"] == "intimacy-architect-sub-01"
    assert body["to_tier"] == "platinum_assist"
    assert body["award_lb_after"] == 4.0
    assert "Soul Slot" in body["promotion_title"]


def test_crown_boss_sr_gifts(crown_client: TestClient) -> None:
    response = crown_client.get("/api/v1/workforce/crown/gifts")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] >= 6
    ids = {gift["id"] for gift in body["gifts"]}
    assert "cosign-v1" in ids
    assert "platinum-5k-ledger" in ids


def test_crown_cosign_record(crown_client: TestClient) -> None:
    post = crown_client.post(
        "/api/v1/workforce/crown/cosign",
        json={
            "signer": "Gary B (Boss Sr.)",
            "message": "Crown Completion v1.0 — the empire stands. Long live the fleet.",
        },
    )
    assert post.status_code == 200
    assert post.json()["signer"] == "Gary B (Boss Sr.)"

    listing = crown_client.get("/api/v1/workforce/crown/cosign")
    assert listing.status_code == 200
    assert listing.json()["count"] >= 1


def test_roster_platinum_enrichment() -> None:
    roster = get_roster()
    assert len(roster) == len(WORKFORCE_ROSTER)
    for member in roster:
        assert member.get("award_platinum") is True
        assert member.get("platinum_value_usd") == 5000.0

    assist = next(m for m in roster if m["id"] == "intimacy-architect-sub-01")
    assert assist["tier"] == "platinum_assist"
    assert assist["award_lb_gold"] == 4.0
    assert assist.get("promoted") is True


def test_dispatch_crown_legacy_skill(crown_client: TestClient) -> None:
    member = next(m for m in WORKFORCE_ROSTER if m["codename"] == "CrownCompletion_Legacy_Sub_01")
    dispatch = crown_client.post(
        "/api/v1/workforce/theater/dispatch",
        json={
            "member_id": member["id"],
            "prompt": "Archive crown legacy",
            "skill": "Crown_Legacy_Archive",
        },
    )
    assert dispatch.status_code == 200
    task_id = dispatch.json()["id"]

    for _ in range(30):
        detail = crown_client.get(f"/api/v1/workforce/theater/tasks/{task_id}")
        assert detail.status_code == 200
        current = detail.json()
        if current["status"] == "completed":
            assert current["result"]
            assert "Crown Completion" in current["result"]
            break
        if current["status"] == "failed":
            pytest.fail(current.get("error") or "task failed")
    else:
        pytest.fail("task did not complete in time")


def test_crown_grant_all_boss_sr_yes(crown_client: TestClient) -> None:
    response = crown_client.post("/api/v1/workforce/crown/grant-all")
    assert response.status_code == 200
    body = response.json()
    assert body["boss_sr_accepted_all"] is True
    assert body["gifts_granted"] == 8
    assert body["platinum_ledger_entries"] == 26
    assert body["revenue_bonuses_applied"] is True
    assert body["live_headline_session_id"]
    assert body["creative_session_id"]

    granted = crown_client.get("/api/v1/workforce/crown/granted")
    assert granted.status_code == 200
    assert granted.json()["count"] == 8
    assert granted.json()["boss_sr_accepted_all"] is True

    cosigns = crown_client.get("/api/v1/workforce/crown/cosign")
    assert cosigns.json()["count"] >= 2

    sessions = crown_client.get("/api/v1/workforce/crown/sessions")
    assert sessions.status_code == 200
    assert sessions.json()["count"] >= 1

    revenue_schema = crown_client.get("/api/v1/workforce/revenue/schema")
    assert revenue_schema.status_code == 200
    sub = revenue_schema.json()["subscription_share"]
    assert sub["tiers"]["platinum_assist"] == 0.12
    assert sub["phase_top3_bonus"]["enabled"] is True

    repeat = crown_client.post("/api/v1/workforce/crown/grant-all")
    assert repeat.status_code == 200
    assert repeat.json()["platinum_ledger_entries"] == 0


def test_crown_completion_service_defaults(tmp_path: Path) -> None:
    crown = CrownCompletion(
        schema_path=str(tmp_path / "schema.json"),
        cosign_path=str(tmp_path / "cosign.json"),
    )
    assert len(crown.list_phase_rankings()) == 3
    assert len(crown.build_platinum_awards()) == len(WORKFORCE_ROSTER)
    assert crown.get_promotion()["member_id"] == "intimacy-architect-sub-01"