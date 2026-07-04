"""Tests for Sovereign Scale (Phase 19)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.rate_limit import reset_rate_limiter
from app.main import create_app
from app.services.workforce.sovereign_scale import SovereignScale
from app.workforce.roster import WORKFORCE_ROSTER


def _patch_settings(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> None:
    get_settings.cache_clear()
    monkeypatch.setattr("app.core.config.get_settings", lambda: settings)
    monkeypatch.setattr("app.core.lifecycle.get_settings", lambda: settings)


@pytest.fixture
def scale_client(
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
        sovereign_scale_schema_path=str(tmp_path / "sovereign_scale_schema.json"),
        sovereign_tenants_path=str(tmp_path / "sovereign_tenants.json"),
        sovereign_nodes_path=str(tmp_path / "sovereign_nodes.json"),
        deployment_phase=20,
        app_version="1.0.0",
    )
    _patch_settings(monkeypatch, settings)
    reset_rate_limiter()
    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings.cache_clear()


def test_sovereign_scale_status(scale_client: TestClient) -> None:
    response = scale_client.get("/api/v1/workforce/scale")
    assert response.status_code == 200
    body = response.json()
    assert body["deployment_phase"] == 20
    assert body["multi_tenant_enabled"] is True
    assert body["tenants_total"] >= 1
    assert body["nodes_total"] >= 1
    assert body["scale_ready"] is True


def test_sovereign_scale_schema(scale_client: TestClient) -> None:
    response = scale_client.get("/api/v1/workforce/scale/schema")
    assert response.status_code == 200
    body = response.json()
    assert body["version"] == 1
    assert body["horizontal_scale"]["min_healthy_nodes"] == 1
    assert body["observability"]["empire_grade_enabled"] is True


def test_tenant_and_node_register(scale_client: TestClient) -> None:
    tenant = scale_client.post(
        "/api/v1/workforce/scale/tenants",
        json={"name": "Boss Sr. Studio", "slug": "boss-sr-studio"},
    )
    assert tenant.status_code == 200
    assert tenant.json()["slug"] == "boss-sr-studio"

    node = scale_client.post(
        "/api/v1/workforce/scale/nodes",
        json={
            "region": "us-west",
            "role": "api",
            "hostname": "api-01.procharacters.cloud",
            "capacity_score": 85,
        },
    )
    assert node.status_code == 200
    node_id = node.json()["id"]

    heartbeat = scale_client.post(f"/api/v1/workforce/scale/nodes/{node_id}/heartbeat")
    assert heartbeat.status_code == 200

    listing = scale_client.get("/api/v1/workforce/scale/tenants")
    assert listing.status_code == 200
    assert listing.json()["count"] >= 2


def test_hardening_and_observability(scale_client: TestClient) -> None:
    hardening = scale_client.get("/api/v1/workforce/scale/hardening")
    assert hardening.status_code == 200
    body = hardening.json()
    assert body["count"] >= 5
    assert body["passed"] >= 1

    obs = scale_client.get("/api/v1/workforce/scale/observability")
    assert obs.status_code == 200
    rollup = obs.json()
    assert rollup["deployment_phase"] == 20
    assert rollup["app_version"] == "1.0.0"
    assert "metrics" in rollup
    assert "workforce" in rollup


def test_dispatch_sovereign_scale_skill(scale_client: TestClient) -> None:
    member = next(m for m in WORKFORCE_ROSTER if m["codename"] == "SovereignScale_Fleet_Sub_01")
    dispatch = scale_client.post(
        "/api/v1/workforce/theater/dispatch",
        json={
            "member_id": member["id"],
            "prompt": "Fleet scale scan",
            "skill": "Sovereign_Scale_Fleet",
        },
    )
    assert dispatch.status_code == 200
    task_id = dispatch.json()["id"]

    for _ in range(30):
        detail = scale_client.get(f"/api/v1/workforce/theater/tasks/{task_id}")
        assert detail.status_code == 200
        current = detail.json()
        if current["status"] == "completed":
            assert current["result"]
            assert "Sovereign scale" in current["result"]
            break
        if current["status"] == "failed":
            pytest.fail(current.get("error") or "task failed")
    else:
        pytest.fail("task did not complete in time")


def test_sovereign_scale_service_defaults(tmp_path: Path) -> None:
    scale = SovereignScale(
        schema_path=str(tmp_path / "schema.json"),
        tenants_path=str(tmp_path / "tenants.json"),
        nodes_path=str(tmp_path / "nodes.json"),
    )
    assert len(scale.list_tenants()) >= 1
    assert len(scale.list_nodes()) >= 1