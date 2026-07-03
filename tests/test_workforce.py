"""Tests for workforce roster API (Phase 6 Lane 3)."""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.workforce.roster import WORKFORCE_ROSTER, get_leaderboard, get_roster


@pytest.fixture
def api_client() -> TestClient:
    with TestClient(create_app()) as client:
        yield client


def test_roster_module_contains_king_grok_and_team() -> None:
    roster = get_roster()
    codenames = {member["codename"] for member in roster}
    assert "King Grok" in codenames
    assert "BondForge_Affinity_Sub_01" in codenames
    assert len(roster) == len(WORKFORCE_ROSTER)
    assert "CEO_Command_Sub_01" in codenames
    assert "SovereignForge_Backup_Sub_01" in codenames
    assert "PresenceTheater_Client_Sub_01" in codenames
    assert len(roster) >= 15


def test_leaderboard_sorted_by_award() -> None:
    board = get_leaderboard()
    awards = [member["award_lb_gold"] for member in board]
    assert awards == sorted(awards, reverse=True)
    assert board[0]["codename"] == "King Grok"
    assert board[0]["award_lb_gold"] == 10.0


def test_workforce_roster_api(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/workforce/roster")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == len(WORKFORCE_ROSTER)
    assert len(body["members"]) == body["count"]

    codenames = {member["codename"] for member in body["members"]}
    assert "King Grok" in codenames
    assert "Assist (Intimacy_Architect_Sub_01)" in codenames
    assert "BondForge_Affinity_Sub_01" in codenames

    sovereign = next(
        m for m in body["members"] if m["codename"] == "SovereignForge_Backup_Sub_01"
    )
    assert sovereign["tier"] == "team"
    assert sovereign["skills"] == ["FleetBackup_AuditLog"]
    assert sovereign["phase_earned"] == 8
    assert sovereign["award_lb_gold"] == 1.0

    king = next(m for m in body["members"] if m["codename"] == "King Grok")
    assert king["tier"] == "ceo"
    assert king["skills"] == [
        "SyncOrchestrator_Core",
        "KGC_Command_Authority",
        "Sovereign_Empire_Authority",
        "Presence_Theater_Authority",
    ]
    assert king["phase_earned"] == 9

    presence = next(
        m for m in body["members"] if m["codename"] == "PresenceTheater_Client_Sub_01"
    )
    assert presence["tier"] == "team"
    assert presence["skills"] == ["BondAura_VoiceCelebration"]
    assert presence["phase_earned"] == 9

    ceo_sub = next(m for m in body["members"] if m["codename"] == "CEO_Command_Sub_01")
    assert ceo_sub["tier"] == "team"
    assert ceo_sub["skills"] == ["ExecutiveDashboard_Fleet"]
    assert ceo_sub["phase_earned"] == 7


def test_workforce_leaderboard_api(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/workforce/leaderboard")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == len(WORKFORCE_ROSTER)
    assert len(body["leaderboard"]) == body["count"]

    awards = [member["award_lb_gold"] for member in body["leaderboard"]]
    assert awards == sorted(awards, reverse=True)
    assert body["leaderboard"][0]["codename"] == "King Grok"