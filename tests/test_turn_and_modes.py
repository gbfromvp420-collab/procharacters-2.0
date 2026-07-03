"""Phase 6 Lane 2: TURN/STUN config, chat modes, SSE resilience headers, session metadata."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.rate_limit import reset_rate_limiter
from app.main import create_app
from app.api.routes.chat import _sse_resilience_headers
from app.models.llm import ChatMessage
from app.services.companion.store import SessionCompanionStore
from app.services.webrtc.session_manager import WebRTCSessionManager


def _patch_settings(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> None:
    get_settings.cache_clear()
    monkeypatch.setattr("app.core.config.get_settings", lambda: settings)
    monkeypatch.setattr("app.core.lifecycle.get_settings", lambda: settings)


@pytest.fixture
def lane2_settings(tmp_path: Path) -> Settings:
    return Settings(
        llm_provider="mock",
        tts_provider="mock",
        video_provider="mock",
        mock_realistic=False,
        provider_gate_enabled=False,
        companion_persist_enabled=True,
        companion_persist_path=str(tmp_path / "companion_sessions.json"),
        kgc_policies_path=str(tmp_path / "kgc_policies.json"),
        api_key_enabled=False,
        rate_limit_enabled=False,
    )


@pytest.fixture
def client(
    monkeypatch: pytest.MonkeyPatch,
    lane2_settings: Settings,
) -> Iterator[TestClient]:
    _patch_settings(monkeypatch, lane2_settings)
    reset_rate_limiter()
    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings.cache_clear()


def test_ice_servers_stun_only_by_default() -> None:
    mgr = WebRTCSessionManager(settings=Settings())
    servers = mgr.ice_servers

    assert len(servers) == 1
    assert servers[0]["urls"] == "stun:stun.l.google.com:19302"


def test_ice_servers_includes_turn_when_credentials_configured() -> None:
    settings = Settings(
        webrtc_turn_urls=["turn:turn.example.com:3478", "turns:turn.example.com:5349"],
        webrtc_turn_username="turn-user",
        webrtc_turn_credential="turn-secret",
    )
    mgr = WebRTCSessionManager(settings=settings)
    servers = mgr.ice_servers

    assert len(servers) == 2
    assert servers[0]["urls"] == "stun:stun.l.google.com:19302"
    assert servers[1]["urls"] == settings.webrtc_turn_urls
    assert servers[1]["username"] == "turn-user"
    assert servers[1]["credential"] == "turn-secret"


def test_ice_servers_omits_turn_without_full_credentials() -> None:
    partial = Settings(
        webrtc_turn_urls=["turn:turn.example.com:3478"],
        webrtc_turn_username="turn-user",
        webrtc_turn_credential="",
    )
    mgr = WebRTCSessionManager(settings=partial)
    assert len(mgr.ice_servers) == 1


def test_webrtc_session_create_returns_turn_ice_servers(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    settings = Settings(
        webrtc_turn_urls=["turn:relay.example.com:3478"],
        webrtc_turn_username="prod-user",
        webrtc_turn_credential="prod-secret",
        provider_gate_enabled=False,
        rate_limit_enabled=False,
    )
    _patch_settings(monkeypatch, settings)
    reset_rate_limiter()

    with TestClient(create_app()) as test_client:
        response = test_client.post("/api/v1/webrtc/session")
        assert response.status_code == 201
        body = response.json()
        session_id = body["session_id"]
        assert len(body["ice_servers"]) == 2
        assert body["ice_servers"][1]["username"] == "prod-user"
        teardown = test_client.delete(f"/api/v1/webrtc/session/{session_id}")
        assert teardown.status_code == 204

    get_settings.cache_clear()


def test_chat_modes_endpoint(client: TestClient) -> None:
    response = client.get("/api/v1/chat/modes")
    assert response.status_code == 200
    assert response.json() == {
        "webrtc": True,
        "sse_perform": True,
        "sse_speak": True,
    }


def test_sse_resilience_headers_when_webrtc_bonded() -> None:
    mgr = WebRTCSessionManager(settings=Settings(companion_persist_enabled=False))
    store = SessionCompanionStore(settings=Settings(companion_persist_enabled=False))
    session = mgr.create_session()

    headers = _sse_resilience_headers(
        session.session_id,
        session_manager=mgr,
        companion_store=store,
    )
    assert headers == {
        "X-Session-Bond": "true",
        "X-Memory-Summary-Present": "false",
    }


def test_sse_resilience_headers_when_memory_present() -> None:
    mgr = WebRTCSessionManager(settings=Settings())
    store = SessionCompanionStore(settings=Settings(companion_persist_enabled=False))
    session_id = "memory-session"
    store.append_turn(
        session_id,
        ChatMessage(role="user", content="Hi"),
        ChatMessage(role="assistant", content="Hello"),
    )

    headers = _sse_resilience_headers(
        session_id,
        session_manager=mgr,
        companion_store=store,
    )
    assert headers == {
        "X-Session-Bond": "false",
        "X-Memory-Summary-Present": "true",
    }


def test_perform_sse_resilience_headers_without_webrtc_bond(client: TestClient) -> None:
    session_id = "sse-only-session"
    payload = {
        "session_id": session_id,
        "use_memory": True,
        "max_tokens": 8,
        "messages": [{"role": "user", "content": "First turn"}],
    }
    first = client.post("/api/v1/chat/perform", json=payload)
    assert first.status_code == 200
    assert first.headers["X-Session-Bond"] == "false"
    assert first.headers["X-Memory-Summary-Present"] == "false"

    second = client.post(
        "/api/v1/chat/perform",
        json={
            **payload,
            "messages": [{"role": "user", "content": "Second turn"}],
        },
    )
    assert second.status_code == 200
    assert second.headers["X-Session-Bond"] == "false"
    assert second.headers["X-Memory-Summary-Present"] == "true"


def test_list_sessions_with_details_includes_created_at() -> None:
    mgr = WebRTCSessionManager(settings=Settings())
    session = mgr.create_session()

    details = mgr.list_sessions_with_details()
    assert len(details) == 1
    assert details[0]["session_id"] == session.session_id
    assert details[0]["created_at"] == session.created_at
    assert details[0]["created_at"]