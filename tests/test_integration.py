"""End-to-end integration tests using FastAPI TestClient."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.rate_limit import reset_rate_limiter
from app.main import create_app


def _patch_settings(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> None:
    get_settings.cache_clear()
    monkeypatch.setattr("app.core.config.get_settings", lambda: settings)
    # lifespan binds get_settings at import time; patch that reference too.
    monkeypatch.setattr("app.core.lifecycle.get_settings", lambda: settings)


@pytest.fixture
def integration_settings(tmp_path: Path) -> Settings:
    return Settings(
        llm_provider="mock",
        tts_provider="mock",
        video_provider="mock",
        mock_realistic=False,
        provider_gate_enabled=True,
        companion_persist_enabled=True,
        companion_persist_path=str(tmp_path / "companion_sessions.json"),
        kgc_policies_path=str(tmp_path / "kgc_policies.json"),
        api_key_enabled=False,
        api_key="",
        rate_limit_enabled=False,
    )


@pytest.fixture
def client(
    monkeypatch: pytest.MonkeyPatch,
    integration_settings: Settings,
) -> Iterator[TestClient]:
    _patch_settings(monkeypatch, integration_settings)
    reset_rate_limiter()
    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings.cache_clear()


_TERMINAL_SSE_TYPES = {"done", "error", "tts_error", "video_error"}


def _parse_sse_text(body: str) -> list[dict]:
    events: list[dict] = []
    for line in body.splitlines():
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    return events


def _perform_and_collect(client: TestClient, payload: dict) -> list[dict]:
    response = client.post("/api/v1/chat/perform", json=payload)
    assert response.status_code == 200
    return _parse_sse_text(response.text)


def test_health_and_metrics_public(client: TestClient) -> None:
    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    metrics = client.get("/api/v1/metrics")
    assert metrics.status_code == 200
    body = metrics.json()
    assert "perform_requests" in body
    assert "uptime_seconds" in body


def test_full_integration_flow(client: TestClient) -> None:
    created = client.post("/api/v1/webrtc/session")
    assert created.status_code == 201
    session_id = created.json()["session_id"]
    assert session_id

    listed = client.get("/api/v1/webrtc/sessions")
    assert listed.status_code == 200
    listed_body = listed.json()
    assert session_id in listed_body["sessions"]
    assert listed_body["count"] >= 1

    patched = client.patch(
        f"/api/v1/companion/{session_id}/config",
        json={"voice": "warm", "avatar_id": "professional"},
    )
    assert patched.status_code == 200
    assert patched.json()["voice"] == "warm"
    assert patched.json()["avatar_id"] == "professional"

    # Close signaling early so perform does not block on aiortc bridge teardown.
    closed = client.delete(f"/api/v1/webrtc/session/{session_id}")
    assert closed.status_code == 204

    perform_payload = {
        "session_id": session_id,
        "use_memory": True,
        "max_tokens": 16,
        "messages": [{"role": "user", "content": "Say hello in one short sentence."}],
    }
    events = _perform_and_collect(client, perform_payload)

    assert events
    event_types = {event.get("type") for event in events}
    assert "token" in event_types

    history = client.get(f"/api/v1/companion/{session_id}/history")
    assert history.status_code == 200
    history_body = history.json()
    assert history_body["turn_count"] >= 1
    assert any(msg["role"] == "user" for msg in history_body["messages"])


def test_persistence_restart_round_trip(
    monkeypatch: pytest.MonkeyPatch,
    integration_settings: Settings,
) -> None:
    _patch_settings(monkeypatch, integration_settings)
    reset_rate_limiter()

    session_id = "persist-restart-session"
    with TestClient(create_app()) as first_client:
        first_client.patch(
            f"/api/v1/companion/{session_id}/config",
            json={"voice": "bright", "avatar_id": "casual"},
        )

        perform_payload = {
            "session_id": session_id,
            "use_memory": True,
            "max_tokens": 32,
            "messages": [{"role": "user", "content": "Remember this integration test turn."}],
        }
        events = _perform_and_collect(first_client, perform_payload)
        assert any(event.get("type") == "done" for event in events)

    get_settings.cache_clear()
    _patch_settings(monkeypatch, integration_settings)
    reset_rate_limiter()

    with TestClient(create_app()) as restarted_client:
        sessions = restarted_client.get("/api/v1/companion/sessions")
        assert sessions.status_code == 200
        session_ids = {item["id"] for item in sessions.json()}
        assert session_id in session_ids

        config = restarted_client.get(f"/api/v1/companion/{session_id}/config")
        assert config.status_code == 200
        assert config.json()["voice"] == "bright"
        assert config.json()["avatar_id"] == "casual"

        history = restarted_client.get(f"/api/v1/companion/{session_id}/history")
        assert history.status_code == 200
        assert history.json()["turn_count"] >= 1


def test_api_key_required_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
    integration_settings: Settings,
) -> None:
    secured = integration_settings.model_copy(
        update={"api_key_enabled": True, "api_key": "test-secret-key"},
    )
    _patch_settings(monkeypatch, secured)
    reset_rate_limiter()

    with TestClient(create_app()) as secured_client:
        assert secured_client.get("/api/v1/health").status_code == 200
        assert secured_client.get("/api/v1/metrics").status_code == 200

        denied = secured_client.post("/api/v1/webrtc/session")
        assert denied.status_code == 401

        allowed_header = secured_client.post(
            "/api/v1/webrtc/session",
            headers={"X-API-Key": "test-secret-key"},
        )
        assert allowed_header.status_code == 201

        allowed_bearer = secured_client.post(
            "/api/v1/webrtc/session",
            headers={"Authorization": "Bearer test-secret-key"},
        )
        assert allowed_bearer.status_code == 201


def test_rate_limit_triggers(
    monkeypatch: pytest.MonkeyPatch,
    integration_settings: Settings,
) -> None:
    limited = integration_settings.model_copy(
        update={"rate_limit_enabled": True, "rate_limit_perform_per_minute": 2},
    )
    _patch_settings(monkeypatch, limited)
    reset_rate_limiter()

    with TestClient(create_app()) as limited_client:
        first = limited_client.post("/api/v1/webrtc/session")
        second = limited_client.post("/api/v1/webrtc/session")
        third = limited_client.post("/api/v1/webrtc/session")

        assert first.status_code == 201
        assert second.status_code == 201
        assert third.status_code == 429
        assert third.json()["detail"] == "Rate limit exceeded"

        perform_payload = {
            "max_tokens": 8,
            "messages": [{"role": "user", "content": "quick"}],
        }
        for _ in range(2):
            assert _perform_and_collect(limited_client, perform_payload)

        blocked = limited_client.post("/api/v1/chat/perform", json=perform_payload)
        assert blocked.status_code == 429