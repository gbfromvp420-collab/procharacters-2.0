"""Tests for in-memory metrics collector and /metrics API."""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.models.llm import ChatMessage
from app.services.observability.metrics import MetricsCollector


def test_metrics_collector_snapshot():
    metrics = MetricsCollector()
    metrics.increment_perform_requests(2)
    metrics.increment_speak_requests(3)
    metrics.increment_tokens_streamed(10)
    metrics.increment_sessions_created()
    metrics.increment_sessions_closed(2)
    metrics.increment_companion_turns_saved(4)
    metrics.increment_bond_increments(2)

    snapshot = metrics.snapshot()
    assert snapshot == {
        "perform_requests": 2,
        "speak_requests": 3,
        "tokens_streamed": 10,
        "sessions_created": 1,
        "sessions_closed": 2,
        "companion_turns_saved": 4,
        "bond_increments": 2,
    }


def test_metrics_collector_thread_safe_increment():
    metrics = MetricsCollector()
    for _ in range(100):
        metrics.increment_tokens_streamed()
    assert metrics.snapshot()["tokens_streamed"] == 100


@pytest.fixture
def api_client() -> TestClient:
    with TestClient(create_app()) as client:
        yield client


def test_metrics_api_returns_snapshot_and_uptime(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/metrics")
    assert response.status_code == 200
    body = response.json()

    for key in (
        "perform_requests",
        "speak_requests",
        "tokens_streamed",
        "sessions_created",
        "sessions_closed",
        "companion_turns_saved",
        "bond_increments",
        "uptime_seconds",
    ):
        assert key in body
        assert body[key] >= 0


def test_webrtc_create_close_increments_metrics(api_client: TestClient) -> None:
    before = api_client.get("/api/v1/metrics").json()

    created = api_client.post("/api/v1/webrtc/session")
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    mid = api_client.get("/api/v1/metrics").json()
    assert mid["sessions_created"] == before["sessions_created"] + 1

    closed = api_client.delete(f"/api/v1/webrtc/session/{session_id}")
    assert closed.status_code == 204

    after = api_client.get("/api/v1/metrics").json()
    assert after["sessions_closed"] == before["sessions_closed"] + 1


def test_companion_append_turn_increments_metrics() -> None:
    from app.core.config import Settings
    from app.services.companion.store import SessionCompanionStore

    metrics = MetricsCollector()
    settings = Settings(companion_persist_enabled=False)
    store = SessionCompanionStore(settings=settings, metrics=metrics)

    store.append_turn(
        "metrics-session",
        ChatMessage(role="user", content="Hi"),
        ChatMessage(role="assistant", content="Hello"),
    )

    assert metrics.snapshot()["companion_turns_saved"] == 1