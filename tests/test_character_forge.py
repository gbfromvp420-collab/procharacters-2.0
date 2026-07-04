"""Tests for Character Forge (Phase 17)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.rate_limit import reset_rate_limiter
from app.main import create_app
from app.services.workforce.character_forge import CharacterForge
from app.workforce.roster import WORKFORCE_ROSTER


def _patch_settings(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> None:
    get_settings.cache_clear()
    monkeypatch.setattr("app.core.config.get_settings", lambda: settings)
    monkeypatch.setattr("app.core.lifecycle.get_settings", lambda: settings)


@pytest.fixture
def character_client(
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
        character_forge_schema_path=str(tmp_path / "character_forge_schema.json"),
        character_forge_registry_path=str(tmp_path / "character_forge_registry.json"),
        character_forge_residuals_path=str(tmp_path / "character_forge_residuals.json"),
        deployment_phase=17,
        app_version="0.15.0",
    )
    _patch_settings(monkeypatch, settings)
    reset_rate_limiter()
    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings.cache_clear()


def test_character_forge_status(character_client: TestClient) -> None:
    response = character_client.get("/api/v1/workforce/characters")
    assert response.status_code == 200
    body = response.json()
    assert body["deployment_phase"] == 17
    assert body["nsm_enabled"] is True
    assert body["contact_email"] == "gary@procharacters.cloud"
    assert body["characters_total"] == 0


def test_character_forge_schema(character_client: TestClient) -> None:
    response = character_client.get("/api/v1/workforce/characters/schema")
    assert response.status_code == 200
    body = response.json()
    assert body["version"] == 1
    assert body["nsm_program"]["default_residual_percent"] == 100.0
    assert len(body["distribution_pipeline"]["stages"]) >= 3


def test_character_onboard_bind_and_residual(character_client: TestClient) -> None:
    member = next(m for m in WORKFORCE_ROSTER if m["codename"] == "CharacterForge_NSM_Sub_01")
    onboard = character_client.post(
        "/api/v1/workforce/characters/onboard",
        json={
            "member_id": member["id"],
            "display_name": "NSM Smoke Character",
            "distribution_pipeline": True,
        },
    )
    assert onboard.status_code == 200
    created = onboard.json()
    assert created["status"] == "pending"
    assert created["display_name"] == "NSM Smoke Character"
    character_id = created["id"]

    bind = character_client.post(
        "/api/v1/workforce/characters/bind",
        json={"character_id": character_id, "avatar_id": "casual"},
    )
    assert bind.status_code == 200
    bound = bind.json()
    assert bound["avatar_id"] == "casual"
    assert bound["status"] == "active"

    residual = character_client.post(
        "/api/v1/workforce/characters/residuals",
        json={
            "character_id": character_id,
            "asset_type": "video",
            "amount_cents": 3500,
            "description": "Phase 17 residual smoke",
        },
    )
    assert residual.status_code == 200
    assert residual.json()["amount_cents"] == 3500

    listing = character_client.get("/api/v1/workforce/characters/residuals")
    assert listing.status_code == 200
    body = listing.json()
    assert body["count"] >= 1
    assert body["total_cents"] >= 3500


def test_character_distribution_hooks(character_client: TestClient) -> None:
    response = character_client.get("/api/v1/workforce/characters/distribution")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] >= 3
    ids = {hook["id"] for hook in body["hooks"]}
    assert "avatar_bind" in ids
    assert "residual_ledger" in ids


def test_dispatch_character_skill(character_client: TestClient) -> None:
    member = next(m for m in WORKFORCE_ROSTER if m["codename"] == "CharacterForge_NSM_Sub_01")
    dispatch = character_client.post(
        "/api/v1/workforce/theater/dispatch",
        json={
            "member_id": member["id"],
            "prompt": "NSM registry scan",
            "skill": "Character_NSM_Onboarding",
        },
    )
    assert dispatch.status_code == 200
    task_id = dispatch.json()["id"]

    for _ in range(30):
        detail = character_client.get(f"/api/v1/workforce/theater/tasks/{task_id}")
        assert detail.status_code == 200
        current = detail.json()
        if current["status"] == "completed":
            assert current["result"]
            assert "Character forge" in current["result"]
            break
        if current["status"] == "failed":
            pytest.fail(current.get("error") or "task failed")
    else:
        pytest.fail("task did not complete in time")


def test_character_forge_service_defaults(tmp_path: Path) -> None:
    forge = CharacterForge(
        schema_path=str(tmp_path / "schema.json"),
        registry_path=str(tmp_path / "registry.json"),
        residuals_path=str(tmp_path / "residuals.json"),
    )
    schema = forge.get_schema()
    assert schema["nsm_program"]["contact_email"] == "gary@procharacters.cloud"
    snap = forge.snapshot(deployment_phase=17)
    assert snap["characters_total"] == 0