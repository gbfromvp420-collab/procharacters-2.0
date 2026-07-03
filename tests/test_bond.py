"""Tests for companion bond scoring and memory summarization."""

import json
import uuid
from pathlib import Path

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
        companion_system_prompt="You are a test companion.",
        companion_summarize_enabled=True,
        companion_summarize_after_turns=12,
        companion_memory_summary_preview_max=40,
    )
    return SessionCompanionStore(settings=settings)


def _append_turns(store: SessionCompanionStore, session_id: str, count: int) -> None:
    for i in range(count):
        store.append_turn(
            session_id,
            ChatMessage(role="user", content=f"user-{i}"),
            ChatMessage(role="assistant", content=f"assistant-{i}"),
        )


def test_get_bond_defaults_to_zero(store: SessionCompanionStore) -> None:
    assert store.get_bond("bond-default") == 0


def test_increment_bond_clamps_to_range(store: SessionCompanionStore) -> None:
    sid = "bond-clamp"
    store.increment_bond(sid, 95)
    assert store.get_bond(sid) == 95
    store.increment_bond(sid, 20)
    assert store.get_bond(sid) == 100
    store.increment_bond(sid, -200)
    assert store.get_bond(sid) == 0


def test_append_turn_increments_bond_by_default_delta(store: SessionCompanionStore) -> None:
    sid = "bond-default-delta"
    store.append_turn(
        sid,
        ChatMessage(role="user", content="Hi"),
        ChatMessage(role="assistant", content="Hello"),
    )
    assert store.get_bond(sid) == 3


def test_append_turn_romantic_mode_uses_higher_bond_delta(store: SessionCompanionStore) -> None:
    sid = "bond-romantic"
    store.set_config(sid, relationship_mode="romantic")
    store.append_turn(
        sid,
        ChatMessage(role="user", content="Hi"),
        ChatMessage(role="assistant", content="Hello"),
    )
    assert store.get_bond(sid) == 5


def test_append_turn_flirtatious_mode_uses_higher_bond_delta(
    store: SessionCompanionStore,
) -> None:
    sid = "bond-flirtatious"
    store.set_config(sid, relationship_mode="flirtatious")
    store.append_turn(
        sid,
        ChatMessage(role="user", content="Hi"),
        ChatMessage(role="assistant", content="Hello"),
    )
    assert store.get_bond(sid) == 5


def test_bond_score_in_config_and_heartbeat(store: SessionCompanionStore) -> None:
    sid = "bond-config"
    store.append_turn(
        sid,
        ChatMessage(role="user", content="One"),
        ChatMessage(role="assistant", content="Two"),
    )
    cfg = store.get_config(sid)
    assert cfg["bond_score"] == 3


def test_memory_summarization_triggers_after_threshold(store: SessionCompanionStore) -> None:
    sid = "summarize-session"
    _append_turns(store, sid, 13)

    messages = store.get_messages(sid)
    assert len(messages) == 14  # 13 turns - 6 summarized = 7 turns
    state_summary = store.get_config(sid, memory_preview=False)["memory_summary"]
    assert "user-0" in state_summary
    assert "user-5" in state_summary
    assert "user-6" not in state_summary


def test_memory_summary_prepended_in_build_llm_messages(store: SessionCompanionStore) -> None:
    sid = "summary-llm"
    _append_turns(store, sid, 13)

    built = store.build_llm_messages(
        sid,
        [ChatMessage(role="user", content="Latest")],
        use_memory=True,
    )

    assert built[0].role == "system"
    assert built[1].role == "assistant"
    assert built[1].content.startswith("[Memory summary]")
    assert built[-1].content == "Latest"


def test_get_config_returns_truncated_memory_preview(store: SessionCompanionStore) -> None:
    sid = "summary-preview"
    _append_turns(store, sid, 13)

    preview = store.get_config(sid)["memory_summary"]
    full = store.get_config(sid, memory_preview=False)["memory_summary"]
    assert len(preview) <= 40
    assert len(full) > len(preview)
    assert preview.endswith("...")


def test_bond_increments_metric() -> None:
    metrics = MetricsCollector()
    settings = Settings(companion_persist_enabled=False)
    store = SessionCompanionStore(settings=settings, metrics=metrics)

    store.append_turn(
        "metrics-bond",
        ChatMessage(role="user", content="Hi"),
        ChatMessage(role="assistant", content="Hello"),
    )

    assert metrics.snapshot()["bond_increments"] == 1


def test_bond_persisted_round_trip(tmp_path: Path) -> None:
    persist_path = tmp_path / "bond_sessions.json"
    settings = Settings(
        companion_persist_enabled=True,
        companion_persist_path=str(persist_path),
    )
    store = SessionCompanionStore(settings=settings)
    sid = "persist-bond"
    store.set_config(sid, relationship_mode="romantic")
    store.append_turn(
        sid,
        ChatMessage(role="user", content="Hi"),
        ChatMessage(role="assistant", content="Hello"),
    )

    reloaded = SessionCompanionStore(settings=settings)
    assert reloaded.get_bond(sid) == 5
    cfg = reloaded.get_config(sid, memory_preview=False)
    assert cfg["bond_score"] == 5


def test_list_persisted_sessions_includes_bond_score(store: SessionCompanionStore) -> None:
    sid = "listed-bond"
    store.append_turn(
        sid,
        ChatMessage(role="user", content="Hi"),
        ChatMessage(role="assistant", content="Hello"),
    )
    sessions = store.list_persisted_sessions()
    assert sessions[0]["bond_score"] == 3


@pytest.fixture
def api_client() -> TestClient:
    with TestClient(create_app()) as client:
        yield client


def test_config_api_returns_bond_and_memory_summary(api_client: TestClient) -> None:
    session_id = f"api-bond-config-{uuid.uuid4().hex}"
    api_client.patch(
        f"/api/v1/companion/{session_id}/config",
        json={"relationship_mode": "romantic"},
    )

    store: SessionCompanionStore = api_client.app.state.companion_store
    _append_turns(store, session_id, 13)

    response = api_client.get(f"/api/v1/companion/{session_id}/config")
    assert response.status_code == 200
    body = response.json()
    assert body["bond_score"] == 65  # 13 turns * 5
    assert body["memory_summary"]
    assert len(body["memory_summary"]) <= 120


def test_export_includes_bond_and_full_memory_summary(api_client: TestClient) -> None:
    session_id = f"api-bond-export-{uuid.uuid4().hex}"
    store: SessionCompanionStore = api_client.app.state.companion_store
    _append_turns(store, session_id, 13)

    response = api_client.get(
        f"/api/v1/companion/{session_id}/export",
        params={"format": "json"},
    )
    assert response.status_code == 200
    body = json.loads(response.text)
    assert body["config"]["bond_score"] == 39  # 13 turns * 3
    assert "user-0" in body["config"]["memory_summary"]
    assert body["config"]["memory_summary"].endswith("user-5")