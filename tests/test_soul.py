"""Tests for Innovation Lane 2 — Companion Soul."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.rate_limit import reset_rate_limiter
from app.main import create_app
from app.models.llm import ChatMessage
from app.services.companion.soul import resolve_soul_stage
from app.services.companion.store import SessionCompanionStore


def _patch_settings(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> None:
    get_settings.cache_clear()
    monkeypatch.setattr("app.core.config.get_settings", lambda: settings)
    monkeypatch.setattr("app.core.lifecycle.get_settings", lambda: settings)


@pytest.fixture
def store() -> SessionCompanionStore:
    settings = Settings(
        companion_persist_enabled=False,
        companion_system_prompt="You are a test companion.",
    )
    return SessionCompanionStore(settings=settings)


@pytest.fixture
def soul_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[TestClient]:
    settings = Settings(
        llm_provider="mock",
        tts_provider="mock",
        video_provider="mock",
        mock_realistic=False,
        companion_persist_enabled=True,
        companion_persist_path=str(tmp_path / "companion_sessions.json"),
        api_key_enabled=False,
        rate_limit_enabled=False,
        innovation_lanes_path=str(tmp_path / "innovation_lanes.json"),
        deployment_phase=20,
        app_version="1.0.0",
    )
    _patch_settings(monkeypatch, settings)
    reset_rate_limiter()
    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings.cache_clear()


def test_soul_stage_thresholds() -> None:
    assert resolve_soul_stage(0).id == "acquaintance"
    assert resolve_soul_stage(15).id == "familiar"
    assert resolve_soul_stage(40).id == "confidant"
    assert resolve_soul_stage(70).id == "soulbound"
    assert resolve_soul_stage(95).id == "eternal"


def test_pin_and_list_soul_memory(store: SessionCompanionStore) -> None:
    memory = store.pin_soul_memory(
        "soul-1",
        title="July 4th night",
        body="We named the journal.",
    )
    assert memory["title"] == "July 4th night"
    listed = store.list_soul_memories("soul-1")
    assert len(listed) == 1
    assert listed[0]["body"] == "We named the journal."
    snap = store.get_soul_snapshot("soul-1")
    assert snap["memory_count"] == 1
    assert "July 4th night" in str(snap["overlay"])


def test_stage_cross_pins_auto_memory(store: SessionCompanionStore) -> None:
    store.increment_bond("soul-stage", 16)
    memories = store.list_soul_memories("soul-stage")
    assert any(item["source"] == "stage" for item in memories)
    assert store.get_config("soul-stage")["soul_stage"] == "familiar"


def test_soul_overlay_in_llm_messages(store: SessionCompanionStore) -> None:
    store.pin_soul_memory("soul-llm", title="The throne room", body="Continuity first.")
    built = store.build_llm_messages(
        "soul-llm",
        [ChatMessage(role="user", content="Hi")],
        use_memory=False,
    )
    assert "[Soul depth]" in built[0].content
    assert "The throne room" in built[0].content


def test_soul_lane_api(soul_client: TestClient) -> None:
    response = soul_client.get("/api/v1/workforce/innovation/soul")
    assert response.status_code == 200
    body = response.json()
    assert body["lane_id"] == "companion_soul"
    assert body["status"] == "in_progress"
    assert len(body["stages"]) == 5
    assert body["assist_owner"].startswith("Assist")


def test_soul_session_api(soul_client: TestClient) -> None:
    sid = "soul-api"
    pin = soul_client.post(
        f"/api/v1/companion/{sid}/soul/memories",
        json={"title": "First spark", "body": "Boss Sr. said continue building."},
    )
    assert pin.status_code == 200
    assert pin.json()["title"] == "First spark"

    snap = soul_client.get(f"/api/v1/companion/{sid}/soul")
    assert snap.status_code == 200
    assert snap.json()["memory_count"] == 1

    checkin = soul_client.get(f"/api/v1/companion/{sid}/soul/checkin")
    assert checkin.status_code == 200
    assert checkin.json()["greeting"]

    listed = soul_client.get(f"/api/v1/companion/{sid}/soul/memories")
    assert listed.json()["count"] == 1

    cfg = soul_client.get(f"/api/v1/companion/{sid}/config")
    assert cfg.json()["soul_memory_count"] == 1
    assert cfg.json()["soul_stage"] == "acquaintance"


def test_soul_memories_persist(tmp_path: Path) -> None:
    path = tmp_path / "companion_sessions.json"
    settings = Settings(companion_persist_enabled=True, companion_persist_path=str(path))
    first = SessionCompanionStore(settings=settings)
    first.pin_soul_memory("persist-soul", title="Held", body="Do not lose this.")
    first.save_all()

    second = SessionCompanionStore(settings=settings)
    memories = second.list_soul_memories("persist-soul")
    assert memories[0]["title"] == "Held"
