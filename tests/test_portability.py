"""Tests for companion session portability: bundle export, clone, and import."""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.models.llm import ChatMessage
from app.services.companion.store import SessionCompanionStore
from app.services.observability.metrics import MetricsCollector


@pytest.fixture
def store() -> SessionCompanionStore:
    settings = Settings(
        companion_persist_enabled=False,
        companion_system_prompt="Portable companion.",
        companion_avatars=["default", "professional"],
        companion_voices=["default", "warm"],
    )
    return SessionCompanionStore(settings=settings)


@pytest.fixture
def metrics_store() -> SessionCompanionStore:
    settings = Settings(companion_persist_enabled=False)
    return SessionCompanionStore(settings=settings, metrics=MetricsCollector())


@pytest.fixture
def api_client() -> TestClient:
    with TestClient(create_app()) as client:
        yield client


def _seed_session(store: SessionCompanionStore, session_id: str) -> None:
    store.set_config(
        session_id,
        avatar_id="professional",
        voice="warm",
        relationship_mode="romantic",
        system_prompt="Custom prompt.",
    )
    store.append_turn(
        session_id,
        ChatMessage(role="user", content="Hello"),
        ChatMessage(role="assistant", content="Hi there!"),
    )
    state = store.get_or_create(session_id)
    state.bond_score = 42
    state.milestones_unlocked = ["first_smile"]
    state.memory_summary = "User greeted warmly."


def test_export_bundle_includes_full_state(store: SessionCompanionStore) -> None:
    sid = "bundle-source"
    _seed_session(store, sid)

    bundle = store.export_bundle(sid)

    assert bundle["session_id"] == sid
    assert bundle["avatar_id"] == "professional"
    assert bundle["voice"] == "warm"
    assert bundle["relationship_mode"] == "romantic"
    assert bundle["system_prompt"] == "Custom prompt."
    assert bundle["bond_score"] == 42
    assert bundle["milestones_unlocked"] == ["first_smile"]
    assert bundle["memory_summary"] == "User greeted warmly."
    assert bundle["turn_count"] == 1
    assert len(bundle["messages"]) == 2
    assert bundle["created_at"]
    assert bundle["last_active_at"]


def test_clone_session_creates_new_id_with_copied_state(store: SessionCompanionStore) -> None:
    sid = "clone-source"
    _seed_session(store, sid)

    new_id = store.clone_session(sid)

    assert new_id != sid
    uuid.UUID(new_id)

    original = store.export_bundle(sid)
    cloned = store.export_bundle(new_id)

    assert cloned["avatar_id"] == original["avatar_id"]
    assert cloned["voice"] == original["voice"]
    assert cloned["relationship_mode"] == original["relationship_mode"]
    assert cloned["system_prompt"] == original["system_prompt"]
    assert cloned["bond_score"] == original["bond_score"]
    assert cloned["milestones_unlocked"] == original["milestones_unlocked"]
    assert cloned["memory_summary"] == original["memory_summary"]
    assert cloned["messages"] == original["messages"]
    assert cloned["turn_count"] == original["turn_count"]
    assert cloned["session_id"] == new_id


def test_import_bundle_creates_new_session(store: SessionCompanionStore) -> None:
    sid = "import-source"
    _seed_session(store, sid)
    bundle = store.export_bundle(sid)
    bundle.pop("session_id")

    imported_id = store.import_bundle(bundle)

    assert imported_id != sid
    imported = store.export_bundle(imported_id)
    assert imported["avatar_id"] == bundle["avatar_id"]
    assert imported["messages"] == bundle["messages"]
    assert imported["bond_score"] == bundle["bond_score"]
    assert imported["milestones_unlocked"] == bundle["milestones_unlocked"]
    assert imported["memory_summary"] == bundle["memory_summary"]


def test_import_bundle_uses_requested_session_id_when_free(store: SessionCompanionStore) -> None:
    bundle = {
        "session_id": "requested-import-id",
        "avatar_id": "default",
        "voice": "default",
        "system_prompt": "Imported.",
        "messages": [],
    }

    imported_id = store.import_bundle(bundle)

    assert imported_id == "requested-import-id"
    assert store.get_config(imported_id)["system_prompt"] == "Imported."


def test_import_bundle_generates_uuid_when_session_id_collides(
    store: SessionCompanionStore,
) -> None:
    existing = "collision-id"
    store.get_or_create(existing)
    bundle = {
        "session_id": existing,
        "avatar_id": "professional",
        "voice": "warm",
        "messages": [{"role": "user", "content": "Imported"}],
    }

    imported_id = store.import_bundle(bundle)

    assert imported_id != existing
    uuid.UUID(imported_id)
    assert store.get_messages(imported_id)[0].content == "Imported"


def test_import_bundle_accepts_nested_config_block(store: SessionCompanionStore) -> None:
    bundle = {
        "config": {
            "avatar_id": "professional",
            "voice": "warm",
            "system_prompt": "Nested config.",
            "relationship_mode": "deep",
            "bond_score": 55,
            "memory_summary": "Nested memory.",
            "created_at": "2026-01-01T00:00:00+00:00",
            "last_active_at": "2026-01-02T00:00:00+00:00",
        },
        "milestones_unlocked": ["deep_trust"],
        "messages": [{"role": "assistant", "content": "Welcome back."}],
    }

    imported_id = store.import_bundle(bundle)
    exported = store.export_bundle(imported_id)

    assert exported["avatar_id"] == "professional"
    assert exported["relationship_mode"] == "deep"
    assert exported["bond_score"] == 55
    assert exported["memory_summary"] == "Nested memory."
    assert exported["milestones_unlocked"] == ["deep_trust"]
    assert exported["messages"][0]["content"] == "Welcome back."


def test_clone_and_import_increment_metrics(metrics_store: SessionCompanionStore) -> None:
    sid = "metrics-source"
    _seed_session(metrics_store, sid)
    bundle = metrics_store.export_bundle(sid)

    metrics_store.clone_session(sid)
    metrics_store.import_bundle(bundle)

    snapshot = metrics_store._metrics.snapshot()  # noqa: SLF001
    assert snapshot["sessions_cloned"] == 1
    assert snapshot["sessions_imported"] == 1


def test_bundle_api_endpoint(api_client: TestClient) -> None:
    session_id = "api-bundle-session"
    api_client.patch(
        f"/api/v1/companion/{session_id}/config",
        json={"avatar_id": "professional", "voice": "warm", "relationship_mode": "deep"},
    )
    api_client.post(
        f"/api/v1/companion/{session_id}/heartbeat",
    )

    response = api_client.get(f"/api/v1/companion/{session_id}/bundle")
    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == session_id
    assert body["avatar_id"] == "professional"
    assert body["voice"] == "warm"
    assert body["relationship_mode"] == "deep"
    assert "milestones_unlocked" in body
    assert "memory_summary" in body
    assert "created_at" in body
    assert "last_active_at" in body


def test_clone_api_endpoint(api_client: TestClient) -> None:
    session_id = "api-clone-source"
    api_client.patch(
        f"/api/v1/companion/{session_id}/config",
        json={"voice": "warm", "relationship_mode": "friendly"},
    )

    response = api_client.post(f"/api/v1/companion/{session_id}/clone")
    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] != session_id
    assert body["config"]["voice"] == "warm"
    assert body["config"]["relationship_mode"] == "friendly"


def test_import_api_endpoint(api_client: TestClient) -> None:
    bundle = {
        "avatar_id": "default",
        "voice": "default",
        "system_prompt": "Imported via API.",
        "relationship_mode": "friendly",
        "bond_score": 10,
        "milestones_unlocked": [],
        "memory_summary": "API import.",
        "messages": [{"role": "user", "content": "Hi"}],
        "turn_count": 0,
        "created_at": "2026-03-01T12:00:00+00:00",
        "last_active_at": "2026-03-01T12:00:00+00:00",
    }

    response = api_client.post("/api/v1/companion/import", json=bundle)
    assert response.status_code == 200
    body = response.json()
    assert body["session_id"]

    cfg = api_client.get(f"/api/v1/companion/{body['session_id']}/config").json()
    assert cfg["system_prompt"] == "Imported via API."
    assert cfg["memory_summary"]


def test_clone_and_import_api_increment_metrics(api_client: TestClient) -> None:
    before = api_client.get("/api/v1/metrics").json()
    session_id = "api-metrics-source"
    api_client.patch(
        f"/api/v1/companion/{session_id}/config",
        json={"voice": "warm"},
    )

    clone_resp = api_client.post(f"/api/v1/companion/{session_id}/clone")
    assert clone_resp.status_code == 200
    bundle = api_client.get(f"/api/v1/companion/{session_id}/bundle").json()
    import_resp = api_client.post("/api/v1/companion/import", json=bundle)
    assert import_resp.status_code == 200

    after = api_client.get("/api/v1/metrics").json()
    assert after["sessions_cloned"] == before["sessions_cloned"] + 1
    assert after["sessions_imported"] == before["sessions_imported"] + 1