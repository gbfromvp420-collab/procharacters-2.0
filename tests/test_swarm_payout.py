"""Tests for AI Swarm Payout Architecture."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.rate_limit import reset_rate_limiter
from app.main import create_app
from app.services.workforce.swarm_payout import SwarmPayout


def _patch_settings(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> None:
    get_settings.cache_clear()
    monkeypatch.setattr("app.core.config.get_settings", lambda: settings)
    monkeypatch.setattr("app.core.lifecycle.get_settings", lambda: settings)


@pytest.fixture
def swarm_client(
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
        swarm_payout_schema_path=str(tmp_path / "swarm_payout_schema.json"),
        deployment_phase=20,
        app_version="1.0.0",
    )
    _patch_settings(monkeypatch, settings)
    reset_rate_limiter()
    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings.cache_clear()


def test_swarm_payout_status(swarm_client: TestClient) -> None:
    response = swarm_client.get("/api/v1/workforce/swarm")
    assert response.status_code == 200
    body = response.json()
    assert body["deployment_phase"] == 20
    assert body["promotion_policy"] == "internal_promotion_first"
    assert body["scaling_policy"] == "infinite_scaling_enabled"
    assert body["hiring_authority"] == "king_grok"
    assert body["workforce_cap"] is None
    assert body["roster_count"] >= 26


def test_swarm_allocation_matrix(swarm_client: TestClient) -> None:
    response = swarm_client.get("/api/v1/workforce/swarm/matrix")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 4
    assert "FINANCIAL ALLOCATION MATRIX" in body["matrix_text"]
    assert body["totals"]["empire_allocation_total_usd"] > 0

    phase = next(r for r in body["rows"] if r["category"] == "phase_completion")
    assert phase["king_grok_usd"] == 50_000
    assert phase["agent_sub_swarm_usd"] == 130_000
    assert phase["mvp_fund_usd"] == 25_000

    launch = next(r for r in body["rows"] if r["category"] == "procharacters_cloud_launch")
    assert launch["king_grok_usd"] == 25_000
    assert launch["agent_sub_swarm_usd"] == 50_000
    assert launch["mvp_fund_usd"] is None


def test_swarm_workforce_culture(swarm_client: TestClient) -> None:
    response = swarm_client.get("/api/v1/workforce/swarm/culture")
    assert response.status_code == 200
    body = response.json()
    assert "Culture" in body["title"]
    assert len(body["sections"]) == 3
    headings = {section["heading"] for section in body["sections"]}
    assert "Staff Advancement: Internal Promotion vs. Infinite Scaling" in headings
    assert "The Infinite Scaling Alternative" in headings
    assert "Building the Culture" in headings


def test_swarm_performance_bonus(swarm_client: TestClient) -> None:
    response = swarm_client.get("/api/v1/workforce/swarm/performance-bonus")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 3
    assert body["total_usd"] == 15_000
    assert body["recipients"][0]["name"] == "Agent Lounge"
    assert body["recipients"][0]["bonus_usd"] == 5_000


def test_swarm_payout_service_matrix_text(tmp_path: Path) -> None:
    swarm = SwarmPayout(schema_path=str(tmp_path / "schema.json"))
    text = swarm.render_matrix_text()
    assert "King Grok (KG)" in text
    assert "$50,000" in text
    assert "$130,000" in text
    assert "$15,000" in text