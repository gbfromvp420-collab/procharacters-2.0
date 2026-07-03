"""Tests for SessionCompanionStore and multi-turn message assembly."""

import json

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.models.llm import ChatMessage
from app.services.companion.catalog import get_relationship_mode_overlay
from app.services.companion.store import SessionCompanionStore
from app.services.webrtc.session_manager import WebRTCSessionManager


@pytest.fixture
def store() -> SessionCompanionStore:
    settings = Settings(
        companion_persist_enabled=False,
        companion_system_prompt="You are a test companion.",
        companion_avatars=["default", "professional", "casual"],
        companion_voices=["default", "warm", "bright"],
        companion_max_history_turns=3,
    )
    return SessionCompanionStore(settings=settings)


def test_get_or_create_defaults(store: SessionCompanionStore):
    sid = "sess-1"
    cfg = store.get_config(sid)

    assert cfg["avatar_id"] == "default"
    assert cfg["voice"] == "default"
    assert cfg["system_prompt"] == "You are a test companion."
    assert store.get_messages(sid) == []


def test_set_config_partial_update(store: SessionCompanionStore):
    sid = "sess-2"
    store.set_config(sid, voice="warm", avatar_id="casual")

    cfg = store.get_config(sid)
    assert cfg["voice"] == "warm"
    assert cfg["avatar_id"] == "casual"
    assert cfg["system_prompt"] == "You are a test companion."


def test_append_turn_and_history(store: SessionCompanionStore):
    sid = "sess-3"
    user = ChatMessage(role="user", content="Hello")
    assistant = ChatMessage(role="assistant", content="Hi there!")

    store.append_turn(sid, user, assistant)
    history = store.get_messages(sid)

    assert history == [user, assistant]
    assert store.get_config(sid)["voice"] == "default"


def test_clear_history_keeps_config(store: SessionCompanionStore):
    sid = "sess-4"
    store.set_config(sid, voice="bright")
    store.append_turn(
        sid,
        ChatMessage(role="user", content="One"),
        ChatMessage(role="assistant", content="Two"),
    )

    store.clear_history(sid)

    assert store.get_messages(sid) == []
    assert store.get_config(sid)["voice"] == "bright"


def test_remove_session(store: SessionCompanionStore):
    sid = "sess-5"
    store.append_turn(
        sid,
        ChatMessage(role="user", content="x"),
        ChatMessage(role="assistant", content="y"),
    )

    removed = store.remove(sid)
    assert removed is True
    assert store.remove(sid) is False

    # get_or_create re-initializes after remove
    cfg = store.get_config(sid)
    assert cfg["voice"] == "default"
    assert store.get_messages(sid) == []


def test_history_trim_by_max_turns(store: SessionCompanionStore):
    sid = "sess-6"
    for i in range(5):
        store.append_turn(
            sid,
            ChatMessage(role="user", content=f"u{i}"),
            ChatMessage(role="assistant", content=f"a{i}"),
        )

    history = store.get_messages(sid)
    assert len(history) == 6  # 3 turns * 2 messages
    assert history[0].content == "u2"
    assert history[-1].content == "a4"


def test_build_llm_messages_with_memory(store: SessionCompanionStore):
    sid = "sess-7"
    store.append_turn(
        sid,
        ChatMessage(role="user", content="Earlier question"),
        ChatMessage(role="assistant", content="Earlier answer"),
    )

    built = store.build_llm_messages(
        sid,
        [ChatMessage(role="user", content="Follow-up")],
        use_memory=True,
    )

    assert built[0] == ChatMessage(role="system", content="You are a test companion.")
    assert built[1].content == "Earlier question"
    assert built[2].content == "Earlier answer"
    assert built[3].content == "Follow-up"


def test_build_llm_messages_without_memory(store: SessionCompanionStore):
    sid = "sess-8"
    store.append_turn(
        sid,
        ChatMessage(role="user", content="Old"),
        ChatMessage(role="assistant", content="Stale"),
    )

    built = store.build_llm_messages(
        sid,
        [ChatMessage(role="user", content="Fresh")],
        use_memory=False,
    )

    assert len(built) == 2
    assert built[0].role == "system"
    assert built[1].content == "Fresh"


def test_multi_turn_message_building_accumulates_context(store: SessionCompanionStore):
    sid = "multi-turn"
    turns = [
        ("What is 2+2?", "Four."),
        ("And 3+3?", "Six."),
    ]

    for user_text, assistant_text in turns:
        prior = store.build_llm_messages(
            sid,
            [ChatMessage(role="user", content=user_text)],
            use_memory=True,
        )
        assert prior[-1].content == user_text
        store.append_turn(
            sid,
            ChatMessage(role="user", content=user_text),
            ChatMessage(role="assistant", content=assistant_text),
        )

    final = store.build_llm_messages(
        sid,
        [ChatMessage(role="user", content="Sum those answers?")],
        use_memory=True,
    )

    assert final[0].role == "system"
    assert [m.content for m in final[1:-1]] == [
        "What is 2+2?",
        "Four.",
        "And 3+3?",
        "Six.",
    ]
    assert final[-1].content == "Sum those answers?"


@pytest.mark.asyncio
async def test_webrtc_close_keeps_companion_state(store: SessionCompanionStore):
    settings = Settings(companion_persist_enabled=False)
    mgr = WebRTCSessionManager(settings=settings, companion_store=store)
    session = mgr.create_session()
    sid = session.session_id

    store.append_turn(
        sid,
        ChatMessage(role="user", content="hello"),
        ChatMessage(role="assistant", content="hi"),
    )
    assert len(store.get_messages(sid)) == 2

    closed = await mgr.close_session(sid)
    assert closed is True
    assert len(store.get_messages(sid)) == 2
    assert store.get_config(sid)["turn_count"] == 1


def test_set_relationship_mode(store: SessionCompanionStore):
    sid = "sess-relationship"
    store.set_config(sid, relationship_mode="romantic")

    cfg = store.get_config(sid)
    assert cfg["relationship_mode"] == "romantic"


def test_build_llm_messages_appends_relationship_overlay(store: SessionCompanionStore):
    sid = "sess-overlay"
    settings = store._settings  # noqa: SLF001
    store.set_config(sid, relationship_mode="flirtatious")

    built = store.build_llm_messages(
        sid,
        [ChatMessage(role="user", content="Hello")],
        use_memory=False,
    )

    overlay = get_relationship_mode_overlay(settings, "flirtatious")
    assert overlay
    assert overlay in built[0].content
    assert built[0].content.startswith("You are a test companion.")


def test_build_llm_messages_without_relationship_mode_has_no_overlay(
    store: SessionCompanionStore,
):
    sid = "sess-no-overlay"
    built = store.build_llm_messages(
        sid,
        [ChatMessage(role="user", content="Hello")],
        use_memory=False,
    )

    assert built[0].content == "You are a test companion."


@pytest.fixture
def api_client() -> TestClient:
    with TestClient(create_app()) as client:
        yield client


def test_companion_export_json(api_client: TestClient) -> None:
    session_id = "export-json-session"
    api_client.patch(
        f"/api/v1/companion/{session_id}/config",
        json={"relationship_mode": "deep"},
    )
    api_client.post(
        f"/api/v1/companion/{session_id}/heartbeat",
    )

    response = api_client.get(
        f"/api/v1/companion/{session_id}/export",
        params={"format": "json"},
    )
    assert response.status_code == 200
    assert "attachment" in response.headers.get("content-disposition", "")
    body = json.loads(response.text)
    assert body["session_id"] == session_id
    assert body["config"]["relationship_mode"] == "deep"


def test_companion_export_txt(api_client: TestClient) -> None:
    session_id = "export-txt-session"
    response = api_client.get(
        f"/api/v1/companion/{session_id}/export",
        params={"format": "txt"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert f"Session: {session_id}" in response.text


def test_companion_heartbeat(api_client: TestClient) -> None:
    session_id = "heartbeat-session"
    response = api_client.post(f"/api/v1/companion/{session_id}/heartbeat")
    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == session_id
    assert body["status"] == "active"
    assert body["turn_count"] == 0
    assert body["last_active_at"]