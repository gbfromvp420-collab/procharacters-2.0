"""Tests for Presence Theater layer (Phase 9)."""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.companion.presence import (
    BOND_PRESENCE_TIERS,
    get_presence_config,
    resolve_bond_tier,
)


@pytest.fixture
def api_client() -> TestClient:
    with TestClient(create_app()) as client:
        yield client


def test_resolve_bond_tier_thresholds() -> None:
    assert resolve_bond_tier(0).id == "spark"
    assert resolve_bond_tier(24).id == "spark"
    assert resolve_bond_tier(25).id == "warmth"
    assert resolve_bond_tier(49).id == "warmth"
    assert resolve_bond_tier(50).id == "trust"
    assert resolve_bond_tier(74).id == "trust"
    assert resolve_bond_tier(75).id == "depth"
    assert resolve_bond_tier(99).id == "depth"
    assert resolve_bond_tier(100).id == "inseparable"


def test_presence_config_serializes_all_tiers() -> None:
    config = get_presence_config()
    assert config["celebration_enabled"] is True
    assert config["voice_input_enabled"] is True
    assert len(config["bond_tiers"]) == len(BOND_PRESENCE_TIERS)
    assert config["bond_tiers"][0]["id"] == "spark"
    assert config["bond_tiers"][-1]["id"] == "inseparable"


def test_presence_config_api(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/companion/presence")
    assert response.status_code == 200
    body = response.json()

    assert body["celebration_enabled"] is True
    assert body["voice_input_enabled"] is True
    assert body["voice_input_hint"]
    assert len(body["bond_tiers"]) == 5
    assert body["bond_tiers"][2]["label"] == "Trusted"
    assert body["bond_tiers"][2]["min_bond"] == 50