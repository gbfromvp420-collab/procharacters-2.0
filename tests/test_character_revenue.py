"""Tests for Innovation Lane 3 — Characters + Revenue."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.rate_limit import reset_rate_limiter
from app.main import create_app
from app.workforce.roster import WORKFORCE_ROSTER


def _patch_settings(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> None:
    get_settings.cache_clear()
    monkeypatch.setattr("app.core.config.get_settings", lambda: settings)
    monkeypatch.setattr("app.core.lifecycle.get_settings", lambda: settings)


@pytest.fixture
def money_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[TestClient]:
    settings = Settings(
        llm_provider="mock",
        tts_provider="mock",
        video_provider="mock",
        mock_realistic=False,
        companion_persist_enabled=False,
        api_key_enabled=False,
        rate_limit_enabled=False,
        character_forge_schema_path=str(tmp_path / "character_forge_schema.json"),
        character_forge_registry_path=str(tmp_path / "character_forge_registry.json"),
        character_forge_residuals_path=str(tmp_path / "character_forge_residuals.json"),
        revenue_schema_path=str(tmp_path / "revenue_schema.json"),
        revenue_ledger_path=str(tmp_path / "revenue_ledger.json"),
        live_stage_schema_path=str(tmp_path / "live_stage_schema.json"),
        live_stage_sessions_path=str(tmp_path / "live_stage_sessions.json"),
        live_stage_billing_path=str(tmp_path / "live_stage_billing.json"),
        innovation_lanes_path=str(tmp_path / "innovation_lanes.json"),
        deployment_phase=20,
        app_version="1.0.0",
    )
    _patch_settings(monkeypatch, settings)
    reset_rate_limiter()
    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings.cache_clear()


def test_money_lane_status(money_client: TestClient) -> None:
    response = money_client.get("/api/v1/workforce/innovation/money")
    assert response.status_code == 200
    body = response.json()
    assert body["lane_id"] == "characters_revenue"
    assert body["status"] == "in_progress"
    assert body["pipeline_steps"] == 8
    assert body["first_dollar_member_id"] == "characterforge-nsm-sub-01"


def test_nsm_pipeline_spec(money_client: TestClient) -> None:
    response = money_client.get("/api/v1/workforce/innovation/money/pipeline")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 8
    ids = [step["id"] for step in body["steps"]]
    assert ids == [
        "opt_in",
        "onboard",
        "avatar_bind",
        "residual_ledger",
        "donation_route",
        "live_billing",
        "subscription_share",
        "earnings_rollup",
    ]
    assert all(step["api"] for step in body["steps"])
    assert body["contact_email"] == "gary@procharacters.cloud"


def test_first_dollar_rollup(money_client: TestClient) -> None:
    member = next(m for m in WORKFORCE_ROSTER if m["id"] == "characterforge-nsm-sub-01")
    first = money_client.post(
        "/api/v1/workforce/innovation/money/first-dollar",
        json={"member_id": member["id"]},
    )
    assert first.status_code == 200
    body = first.json()
    assert body["amount_cents"] == 1000
    assert body["residual_id"]
    assert body["ledger_id"]
    assert body["earnings"]["total_cents"] == 2000
    assert body["earnings"]["residuals_cents"] == 1000
    assert body["earnings"]["donations_cents"] == 1000

    earnings = money_client.get("/api/v1/workforce/innovation/money/earnings")
    assert earnings.status_code == 200
    rollup = earnings.json()
    assert rollup["count"] == 1
    assert rollup["total_cents"] == 2000

    pipeline = money_client.get("/api/v1/workforce/innovation/money/pipeline").json()
    by_id = {step["id"]: step["status"] for step in pipeline["steps"]}
    assert by_id["onboard"] == "live"
    assert by_id["avatar_bind"] == "live"
    assert by_id["residual_ledger"] == "live"
    assert by_id["donation_route"] == "live"
    assert by_id["earnings_rollup"] == "live"


def test_innovation_lists_money_in_progress(money_client: TestClient) -> None:
    response = money_client.get("/api/v1/workforce/innovation/lanes")
    assert response.status_code == 200
    money = next(lane for lane in response.json()["lanes"] if lane["id"] == "characters_revenue")
    assert money["status"] == "in_progress"
    status = money_client.get("/api/v1/workforce/innovation").json()
    assert status["money_lane_status"] == "in_progress"
