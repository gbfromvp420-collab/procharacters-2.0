"""Tests for companion session persistence and stale-session pruning."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.core.config import Settings
from app.models.llm import ChatMessage
from app.services.companion.persistence import CompanionPersistence
from app.services.companion.store import SessionCompanionStore


@pytest.fixture
def persist_path(tmp_path: Path) -> Path:
    return tmp_path / "companion_sessions.json"


@pytest.fixture
def persist_settings(persist_path: Path) -> Settings:
    return Settings(
        companion_persist_enabled=True,
        companion_persist_path=str(persist_path),
        companion_session_ttl_hours=72,
        companion_system_prompt="Persisted companion.",
        companion_avatars=["default", "professional"],
        companion_voices=["default", "warm"],
    )


def test_persistence_round_trip_save_load(
    persist_settings: Settings,
    persist_path: Path,
):
    store = SessionCompanionStore(settings=persist_settings)
    sid = "round-trip-session"
    store.set_config(sid, voice="warm", avatar_id="professional")
    store.append_turn(
        sid,
        ChatMessage(role="user", content="Hello"),
        ChatMessage(role="assistant", content="Hi!"),
    )

    assert persist_path.exists()

    reloaded = SessionCompanionStore(settings=persist_settings)
    cfg = reloaded.get_config(sid)
    history = reloaded.get_messages(sid)

    assert cfg["voice"] == "warm"
    assert cfg["avatar_id"] == "professional"
    assert cfg["turn_count"] == 1
    assert cfg["created_at"]
    assert cfg["last_active_at"]
    assert history == [
        ChatMessage(role="user", content="Hello"),
        ChatMessage(role="assistant", content="Hi!"),
    ]


def test_persistence_handles_missing_file(persist_settings: Settings, persist_path: Path):
    assert not persist_path.exists()
    store = SessionCompanionStore(settings=persist_settings)
    assert store.list_persisted_sessions() == []


def test_persistence_atomic_write(persist_settings: Settings, persist_path: Path):
    persistence = CompanionPersistence(persist_settings.companion_persist_path)
    persistence.save(
        {
            "sess-a": {
                "avatar_id": "default",
                "voice": "default",
                "system_prompt": "Test",
                "messages": [],
                "created_at": "2026-01-01T00:00:00+00:00",
                "last_active_at": "2026-01-01T00:00:00+00:00",
            }
        }
    )
    loaded = persistence.load()
    assert "sess-a" in loaded
    assert loaded["sess-a"]["avatar_id"] == "default"


def test_prune_stale_sessions(persist_settings: Settings):
    store = SessionCompanionStore(settings=persist_settings)
    fresh_sid = "fresh-session"
    stale_sid = "stale-session"

    store.get_or_create(fresh_sid)
    stale_state = store.get_or_create(stale_sid)
    stale_time = (datetime.now(timezone.utc) - timedelta(hours=100)).isoformat()
    stale_state.last_active_at = stale_time
    store.save_all()

    removed = store.prune_stale(ttl_hours=72)

    assert removed == 1
    assert store.get_config(fresh_sid)["avatar_id"] == "default"
    assert fresh_sid in {item["id"] for item in store.list_persisted_sessions()}
    assert stale_sid not in {item["id"] for item in store.list_persisted_sessions()}


def test_list_persisted_sessions(persist_settings: Settings):
    store = SessionCompanionStore(settings=persist_settings)
    sid = "listed-session"
    store.set_config(sid, avatar_id="professional")
    store.append_turn(
        sid,
        ChatMessage(role="user", content="One"),
        ChatMessage(role="assistant", content="Two"),
    )

    sessions = store.list_persisted_sessions()
    assert len(sessions) == 1
    assert sessions[0]["id"] == sid
    assert sessions[0]["turn_count"] == 1
    assert sessions[0]["avatar_id"] == "professional"
    assert sessions[0]["last_active_at"]


def test_store_without_persistence_is_in_memory_only(tmp_path: Path):
    path = tmp_path / "unused.json"
    settings = Settings(
        companion_persist_enabled=False,
        companion_persist_path=str(path),
    )
    store = SessionCompanionStore(settings=settings)
    store.append_turn(
        "mem-only",
        ChatMessage(role="user", content="x"),
        ChatMessage(role="assistant", content="y"),
    )

    assert not path.exists()

    other = SessionCompanionStore(settings=settings)
    assert other.get_messages("mem-only") == []