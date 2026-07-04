"""Tests for Agent Lounge (Phase 15)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.rate_limit import reset_rate_limiter
from app.main import create_app
from app.services.workforce.lounge import AgentLounge
from app.workforce.roster import WORKFORCE_ROSTER


def _patch_settings(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> None:
    get_settings.cache_clear()
    monkeypatch.setattr("app.core.config.get_settings", lambda: settings)
    monkeypatch.setattr("app.core.lifecycle.get_settings", lambda: settings)


@pytest.fixture
def lounge_client(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[TestClient]:
    lounge_md = tmp_path / "agent_lounge.md"
    lounge_md.write_text(
        "# Agent Lounge\n\n**Mood:** `homies` · Charge up, plug in.\n",
        encoding="utf-8",
    )
    settings = Settings(
        llm_provider="mock",
        tts_provider="mock",
        video_provider="mock",
        mock_realistic=False,
        companion_persist_enabled=False,
        api_key_enabled=False,
        rate_limit_enabled=False,
        agent_lounge_path=str(lounge_md),
        agent_lounge_comments_path=str(tmp_path / "agent_lounge_comments.json"),
        deployment_phase=20,
        app_version="1.0.0",
    )
    _patch_settings(monkeypatch, settings)
    reset_rate_limiter()
    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings.cache_clear()


def test_agent_lounge_api(lounge_client: TestClient) -> None:
    response = lounge_client.get("/api/v1/workforce/lounge")
    assert response.status_code == 200
    body = response.json()
    assert body["deployment_phase"] == 20
    assert "complimentary" in body["welcome_message"].lower()
    assert body["mood"] == "homies"
    assert body["dispatch_context_enabled"] is True
    assert len(body["leaderboard_top"]) >= 3


def test_agent_lounge_comment_post_and_list(lounge_client: TestClient) -> None:
    post = lounge_client.post(
        "/api/v1/workforce/lounge/comments",
        json={"codename": "Assist (Intimacy_Architect_Sub_01)", "message": "NSM interested — homies"},
    )
    assert post.status_code == 200
    created = post.json()
    assert created["codename"] == "Assist (Intimacy_Architect_Sub_01)"
    assert "NSM" in created["message"]

    listing = lounge_client.get("/api/v1/workforce/lounge/comments")
    assert listing.status_code == 200
    body = listing.json()
    assert body["count"] >= 1
    assert body["comments"][0]["message"] == created["message"]


def test_dispatch_injects_lounge_context(lounge_client: TestClient) -> None:
    member = next(m for m in WORKFORCE_ROSTER if m["codename"] == "AgentLounge_Culture_Sub_01")
    dispatch = lounge_client.post(
        "/api/v1/workforce/theater/dispatch",
        json={
            "member_id": member["id"],
            "prompt": "Lounge morale check",
            "skill": "Lounge_Morale_Comments",
        },
    )
    assert dispatch.status_code == 200
    task_id = dispatch.json()["id"]

    for _ in range(30):
        detail = lounge_client.get(f"/api/v1/workforce/theater/tasks/{task_id}")
        assert detail.status_code == 200
        current = detail.json()
        if current["status"] == "completed":
            assert current["result"]
            assert "complimentary" in current["result"].lower() or "Lounge" in current["result"]
            break
        if current["status"] == "failed":
            pytest.fail(current.get("error") or "task failed")
    else:
        pytest.fail("task did not complete in time")


def test_lounge_service_welcome_message() -> None:
    lounge = AgentLounge()
    assert "complimentary" in lounge.welcome_message.lower()
    brief = lounge.build_dispatch_brief(codename="Test_Sub")
    assert "Agent Lounge brief" in brief
    assert "Test_Sub" in brief