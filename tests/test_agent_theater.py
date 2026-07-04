"""Tests for Agent Theater (Phase 13)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.workforce.theater import AgentTheater
from app.workforce.roster import WORKFORCE_ROSTER


@pytest.fixture
def api_client() -> TestClient:
    with TestClient(create_app()) as client:
        yield client


def test_agent_theater_status_api(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/workforce/theater")
    assert response.status_code == 200
    body = response.json()
    assert body["deployment_phase"] == 20
    assert body["dispatchable_count"] == len(WORKFORCE_ROSTER)
    assert body["tasks_total"] == 0
    assert len(body["members"]) == len(WORKFORCE_ROSTER)


def test_agent_theater_dispatch_and_complete(api_client: TestClient) -> None:
    member = next(m for m in WORKFORCE_ROSTER if m["codename"] == "AgentTheater_Dispatch_Sub_01")
    dispatch = api_client.post(
        "/api/v1/workforce/theater/dispatch",
        json={
            "member_id": member["id"],
            "prompt": "Verify contract smoke for TTS provider",
            "skill": "Workforce_TaskDispatch",
        },
    )
    assert dispatch.status_code == 200
    task = dispatch.json()
    assert task["status"] in {"queued", "running", "completed"}
    assert task["codename"] == "AgentTheater_Dispatch_Sub_01"
    assert task["skill"] == "Workforce_TaskDispatch"

    for _ in range(30):
        detail = api_client.get(f"/api/v1/workforce/theater/tasks/{task['id']}")
        assert detail.status_code == 200
        current = detail.json()
        if current["status"] == "completed":
            assert current["result"]
            assert current["duration_ms"] is not None
            assert "Fleet scan" in current["result"] or "fleet" in current["result"].lower()
            break
        if current["status"] == "failed":
            pytest.fail(current.get("error") or "task failed")
    else:
        pytest.fail("task did not complete in time")

    listing = api_client.get("/api/v1/workforce/theater/tasks")
    assert listing.status_code == 200
    listed = listing.json()
    assert listed["count"] >= 1
    assert listed["tasks"][0]["id"] == task["id"]


def test_agent_theater_rejects_unknown_member(api_client: TestClient) -> None:
    response = api_client.post(
        "/api/v1/workforce/theater/dispatch",
        json={"member_id": "missing-agent", "prompt": "hello"},
    )
    assert response.status_code == 404


def test_agent_theater_rejects_invalid_skill(api_client: TestClient) -> None:
    member = WORKFORCE_ROSTER[0]
    response = api_client.post(
        "/api/v1/workforce/theater/dispatch",
        json={
            "member_id": member["id"],
            "prompt": "hello",
            "skill": "Not_A_Real_Skill",
        },
    )
    assert response.status_code == 422


def _workforce_context_from_app(app) -> "WorkforceContext":
    from app.services.workforce.context import WorkforceContext

    return WorkforceContext(
        settings=app.state.settings,
        companion_store=app.state.companion_store,
        session_manager=app.state.session_manager,
        metrics=app.state.metrics,
        provider_probe=app.state.provider_probe,
        kgc_policies=app.state.kgc_policies,
        kgc_audit=app.state.kgc_audit,
        agent_theater=app.state.agent_theater,
        agent_lounge=app.state.agent_lounge,
        revenue_forge=app.state.revenue_forge,
        character_forge=app.state.character_forge,
        live_stage=app.state.live_stage,
        sovereign_scale=app.state.sovereign_scale,
        crown_completion=app.state.crown_completion,
    )


@pytest.mark.asyncio
async def test_agent_theater_service_dispatch(api_client: TestClient) -> None:
    theater: AgentTheater = api_client.app.state.agent_theater
    ctx = _workforce_context_from_app(api_client.app)
    member = next(m for m in WORKFORCE_ROSTER if m["codename"] == "King Grok")
    record = await theater.dispatch(
        member_id=member["id"],
        prompt="Summarize fleet status",
    )
    assert record.status == "queued"
    assert record.skill == member["skills"][0]

    await theater.progress_tasks(ctx)
    current = theater.get_task(record.id)
    assert current is not None
    assert current.status == "completed"
    assert current.result
    assert "Executive dashboard" in current.result