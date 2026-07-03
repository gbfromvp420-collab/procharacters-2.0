"""Tests for bond milestones, persistence, LLM overlays, and SSE unlock events."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.rate_limit import reset_rate_limiter
from app.main import create_app
from app.models.llm import ChatMessage
from app.services.companion.milestones import (
    BOND_MILESTONES,
    check_new_milestone,
    get_milestone_by_id,
    get_milestones_for_ids,
    get_unlocked_milestones,
)
from app.services.companion.store import SessionCompanionStore


@pytest.fixture
def store() -> SessionCompanionStore:
    settings = Settings(
        companion_persist_enabled=False,
        companion_system_prompt="You are a test companion.",
    )
    return SessionCompanionStore(settings=settings)


def test_get_unlocked_milestones_returns_threshold_met() -> None:
    assert get_unlocked_milestones(0) == []
    assert [m.id for m in get_unlocked_milestones(25)] == ["getting_closer"]
    unlocked = get_unlocked_milestones(80)
    assert [m.id for m in unlocked] == [
        "getting_closer",
        "trusted_companion",
        "deep_connection",
    ]


def test_check_new_milestone_detects_crossing() -> None:
    first = BOND_MILESTONES[0]
    assert check_new_milestone(20, 25) == first
    assert check_new_milestone(25, 30) is None
    assert check_new_milestone(30, 20) is None


def test_append_turn_unlocks_and_persists_milestone(store: SessionCompanionStore) -> None:
    sid = "milestone-unlock"
    store.increment_bond(sid, 24)

    milestone = store.append_turn(
        sid,
        ChatMessage(role="user", content="Hi"),
        ChatMessage(role="assistant", content="Hello"),
    )

    assert milestone is not None
    assert milestone.id == "getting_closer"
    assert store.get_bond(sid) == 27
    state = store.get_or_create(sid)
    assert state.milestones_unlocked == ["getting_closer"]


def test_append_turn_does_not_repeat_milestone_unlock(store: SessionCompanionStore) -> None:
    sid = "milestone-repeat"
    store.increment_bond(sid, 24)
    first = store.append_turn(
        sid,
        ChatMessage(role="user", content="One"),
        ChatMessage(role="assistant", content="Two"),
    )
    second = store.append_turn(
        sid,
        ChatMessage(role="user", content="Three"),
        ChatMessage(role="assistant", content="Four"),
    )

    assert first is not None
    assert second is None
    assert store.get_or_create(sid).milestones_unlocked == ["getting_closer"]


def test_milestones_unlocked_persisted_round_trip(tmp_path: Path) -> None:
    persist_path = tmp_path / "milestone_sessions.json"
    settings = Settings(
        companion_persist_enabled=True,
        companion_persist_path=str(persist_path),
    )
    store = SessionCompanionStore(settings=settings)
    sid = "persist-milestones"
    store.increment_bond(sid, 24)
    store.append_turn(
        sid,
        ChatMessage(role="user", content="Hi"),
        ChatMessage(role="assistant", content="Hello"),
    )

    reloaded = SessionCompanionStore(settings=settings)
    state = reloaded.get_or_create(sid)
    assert state.milestones_unlocked == ["getting_closer"]
    assert reloaded.get_bond(sid) == 27


def test_load_backfills_milestones_from_bond_score(tmp_path: Path) -> None:
    persist_path = tmp_path / "legacy_sessions.json"
    persist_path.write_text(
        json.dumps(
            {
                "legacy-session": {
                    "avatar_id": "default",
                    "voice": "default",
                    "system_prompt": "",
                    "relationship_mode": "",
                    "bond_score": 55,
                    "messages": [],
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "last_active_at": "2026-01-01T00:00:00+00:00",
                }
            }
        ),
        encoding="utf-8",
    )
    settings = Settings(
        companion_persist_enabled=True,
        companion_persist_path=str(persist_path),
    )
    store = SessionCompanionStore(settings=settings)
    unlocked = store.get_or_create("legacy-session").milestones_unlocked
    assert unlocked == ["getting_closer", "trusted_companion"]


def test_build_llm_messages_appends_unlocked_milestone_overlays(
    store: SessionCompanionStore,
) -> None:
    sid = "milestone-overlays"
    store.increment_bond(sid, 24)
    store.append_turn(
        sid,
        ChatMessage(role="user", content="Hi"),
        ChatMessage(role="assistant", content="Hello"),
    )

    built = store.build_llm_messages(
        sid,
        [ChatMessage(role="user", content="Latest")],
        use_memory=False,
    )

    first_overlay = get_milestone_by_id("getting_closer")
    assert first_overlay is not None
    assert first_overlay.prompt_overlay in built[0].content


def test_build_llm_messages_stacks_multiple_milestone_overlays(
    store: SessionCompanionStore,
) -> None:
    sid = "milestone-stack"
    state = store.get_or_create(sid)
    state.milestones_unlocked = ["getting_closer", "trusted_companion"]
    state.bond_score = 55

    built = store.build_llm_messages(
        sid,
        [ChatMessage(role="user", content="Hi")],
        use_memory=False,
    )
    system_content = built[0].content
    for milestone_id in ("getting_closer", "trusted_companion"):
        milestone = get_milestone_by_id(milestone_id)
        assert milestone is not None
        assert milestone.prompt_overlay in system_content


def test_get_milestones_for_ids_preserves_threshold_order() -> None:
    ordered = get_milestones_for_ids(["deep_connection", "getting_closer"])
    assert [m.id for m in ordered] == ["getting_closer", "deep_connection"]


@pytest.fixture
def api_client() -> Iterator[TestClient]:
    with TestClient(create_app()) as client:
        yield client


def test_milestones_catalog_api(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/companion/milestones")
    assert response.status_code == 200
    body = response.json()
    assert len(body["milestones"]) == 4
    assert body["milestones"][0]["id"] == "getting_closer"
    assert body["milestones"][0]["bond_threshold"] == 25
    assert body["milestones"][-1]["bond_threshold"] == 100


def _parse_sse_text(body: str) -> list[dict]:
    events: list[dict] = []
    for line in body.splitlines():
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    return events


@pytest.fixture
def perform_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Iterator[TestClient]:
    settings = Settings(
        llm_provider="mock",
        tts_provider="mock",
        video_provider="mock",
        mock_realistic=False,
        provider_gate_enabled=False,
        companion_persist_enabled=False,
        api_key_enabled=False,
        rate_limit_enabled=False,
        companion_persist_path=str(tmp_path / "companion_sessions.json"),
        kgc_policies_path=str(tmp_path / "kgc_policies.json"),
    )
    get_settings.cache_clear()
    monkeypatch.setattr("app.core.config.get_settings", lambda: settings)
    monkeypatch.setattr("app.core.lifecycle.get_settings", lambda: settings)
    reset_rate_limiter()
    with TestClient(create_app()) as client:
        yield client
    get_settings.cache_clear()


def test_perform_emits_bond_milestone_before_done(perform_client: TestClient) -> None:
    session_id = "sse-milestone-session"
    store: SessionCompanionStore = perform_client.app.state.companion_store
    store.increment_bond(session_id, 24)

    response = perform_client.post(
        "/api/v1/chat/perform",
        json={
            "session_id": session_id,
            "use_memory": True,
            "max_tokens": 8,
            "messages": [{"role": "user", "content": "Cross the milestone"}],
        },
    )
    assert response.status_code == 200

    events = _parse_sse_text(response.text)
    milestone_events = [event for event in events if event.get("type") == "bond_milestone"]
    done_events = [event for event in events if event.get("type") == "done"]

    assert len(milestone_events) == 1
    assert milestone_events[0]["milestone_id"] == "getting_closer"
    assert milestone_events[0]["label"] == "Getting Closer"
    assert milestone_events[0]["bond_score"] == 27

    milestone_index = events.index(milestone_events[0])
    done_index = events.index(done_events[0])
    assert milestone_index < done_index