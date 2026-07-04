"""Tests for Orchestration Forge (Phase 14)."""

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


def test_orchestration_status_api(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/workforce/orchestration")
    assert response.status_code == 200
    body = response.json()
    assert body["deployment_phase"] == 20
    assert body["orchestration_enabled"] is True


def test_orchestration_chain_dispatch_and_complete(api_client: TestClient) -> None:
    dispatch_member = next(
        m for m in WORKFORCE_ROSTER if m["codename"] == "AgentTheater_Dispatch_Sub_01"
    )
    forge_member = next(
        m for m in WORKFORCE_ROSTER if m["codename"] == "ProviderForge_Contract_Sub_01"
    )
    response = api_client.post(
        "/api/v1/workforce/orchestration/chain",
        json={
            "steps": [
                {
                    "member_id": dispatch_member["id"],
                    "prompt": "Scan fleet for orchestration smoke",
                    "skill": "Workforce_TaskDispatch",
                },
                {
                    "member_id": forge_member["id"],
                    "prompt": "Verify provider contracts",
                    "skill": "RunPod_ContractSmoke_LiveForge",
                },
            ]
        },
    )
    assert response.status_code == 200
    chain = response.json()
    assert chain["status"] in {"queued", "running", "completed"}
    assert len(chain["steps"]) == 2
    assert chain["first_task_id"]

    for _ in range(60):
        detail = api_client.get(f"/api/v1/workforce/orchestration/chains/{chain['id']}")
        assert detail.status_code == 200
        current = detail.json()
        if current["status"] == "completed":
            assert len(current["task_ids"]) == 2
            break
        if current["status"] == "failed":
            pytest.fail(current.get("error") or "chain failed")
    else:
        pytest.fail("chain did not complete in time")

    tasks = api_client.get("/api/v1/workforce/theater/tasks?limit=10")
    assert tasks.status_code == 200
    task_rows = tasks.json()["tasks"]
    chain_tasks = [row for row in task_rows if row.get("chain_id") == chain["id"]]
    assert len(chain_tasks) >= 2
    assert all(task["orchestrated"] for task in chain_tasks)
    results = " ".join(task.get("result") or "" for task in chain_tasks).lower()
    assert "fleet" in results or "forge_ok" in results


def test_orchestration_rejects_empty_chain(api_client: TestClient) -> None:
    response = api_client.post("/api/v1/workforce/orchestration/chain", json={"steps": []})
    assert response.status_code == 422


def test_theater_dispatch_with_parent(api_client: TestClient) -> None:
    member = next(m for m in WORKFORCE_ROSTER if m["codename"] == "OrchestrationForge_Chain_Sub_01")
    parent = api_client.post(
        "/api/v1/workforce/theater/dispatch",
        json={
            "member_id": member["id"],
            "prompt": "Parent orchestration task",
            "skill": "TaskChain_Orchestration",
        },
    )
    assert parent.status_code == 200
    parent_id = parent.json()["id"]

    child = api_client.post(
        "/api/v1/workforce/theater/dispatch",
        json={
            "member_id": member["id"],
            "prompt": "Child follow-up task",
            "skill": "TaskChain_Orchestration",
            "parent_task_id": parent_id,
        },
    )
    assert child.status_code == 200
    child_body = child.json()
    assert child_body["parent_task_id"] == parent_id
    assert child_body["orchestrated"] is True


def _workforce_context_from_app(app):
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
async def test_agent_theater_real_executor(api_client: TestClient) -> None:
    theater: AgentTheater = api_client.app.state.agent_theater
    ctx = _workforce_context_from_app(api_client.app)
    member = next(m for m in WORKFORCE_ROSTER if m["codename"] == "ProviderForge_Contract_Sub_01")
    record = await theater.dispatch(
        member_id=member["id"],
        prompt="Contract verification smoke",
        skill="RunPod_ContractSmoke_LiveForge",
    )
    await theater.progress_tasks(ctx)
    current = theater.get_task(record.id)
    assert current is not None
    assert current.status == "completed"
    assert current.result
    assert "forge_ok" in current.result


def test_king_grok_orchestration_authority(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/workforce/roster")
    king = next(m for m in response.json()["members"] if m["codename"] == "King Grok")
    assert king["award_lb_gold"] == 21.0
    assert king["phase_earned"] == 20
    assert "Orchestration_Forge_Authority" in king["skills"]
    assert "Revenue_Forge_Authority" in king["skills"]
    assert "Character_Forge_Authority" in king["skills"]
    assert "Live_Stage_Authority" in king["skills"]
    assert "Sovereign_Scale_Authority" in king["skills"]