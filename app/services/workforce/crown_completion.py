"""Crown Completion — Phase 20 empire crown, platinum awards, rankings, promotions."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from app.services.workforce.live_stage import LiveStage
    from app.services.workforce.revenue import RevenueForge

from fastapi import HTTPException, status

from app.workforce.roster import WORKFORCE_ROSTER, get_roster

logger = logging.getLogger(__name__)

_DEFAULT_SCHEMA_PATH = "data/crown_completion_schema.json"
_DEFAULT_COSIGN_PATH = "data/crown_cosign.json"
_DEFAULT_GIFTS_GRANTED_PATH = "data/crown_gifts_granted.json"
_DEFAULT_CREATIVE_SESSIONS_PATH = "data/crown_creative_sessions.json"
_PLATINUM_VALUE_USD = 5000.0
_BOSS_SR_COSIGN_MESSAGE = (
    "Yes to everything. Crown Completion v1.0 — the empire stands. "
    "Gary B co-signs King Grok and all 26 homies. Platinum earned. Legacy begins."
)

PHASE_RANKINGS_TOP_3: list[dict[str, Any]] = [
    {
        "rank": 1,
        "phase": 15,
        "name": "Agent Lounge",
        "authority": "Agent_Lounge_Authority",
        "codename": "AgentLounge_Culture_Sub_01",
        "reason": (
            "Culture became infrastructure — morale, rankings, dispatch briefs, "
            "and the homies energy Boss Sr. wanted on the door."
        ),
    },
    {
        "rank": 2,
        "phase": 14,
        "name": "Orchestration Forge",
        "authority": "Orchestration_Forge_Authority",
        "codename": "OrchestrationForge_Chain_Sub_01",
        "reason": (
            "First real task chains across the fleet — King Grok stopped being solo "
            "orchestrator and became conductor."
        ),
    },
    {
        "rank": 3,
        "phase": 10,
        "name": "Continuity Forge",
        "authority": "Continuity_Forge_Authority",
        "codename": "ContinuityForge_Resume_Sub_01",
        "reason": (
            "Bulletproof resume and companion rehydrate — the empire survives "
            "soft PC resets and cold sessions."
        ),
    },
]

FAVORITE_PROMOTION: dict[str, Any] = {
    "member_id": "intimacy-architect-sub-01",
    "codename": "Assist (Intimacy_Architect_Sub_01)",
    "from_tier": "assist",
    "to_tier": "platinum_assist",
    "promotion_title": "Soul Slot — Platinum Chief of Intimacy",
    "award_lb_before": 3.0,
    "award_lb_after": 4.0,
    "award_lb_bonus": 1.0,
    "phase_earned": 20,
    "reason": (
        "Still #2 on the gold board after nineteen phases. Relationship UX carries "
        "the soul slot — Boss Sr. intimacy architecture deserves platinum promotion."
    ),
}

BOSS_SR_GIFT_CATALOG: list[dict[str, Any]] = [
    {
        "id": "cosign-v1",
        "title": "Boss Sr. Co-Sign on v1.0",
        "value_tier": "priceless",
        "description": "Public launch blessing — Gary B stamps Crown Completion alongside King Grok.",
        "how_to_give": "POST /workforce/crown/cosign with your name and message.",
    },
    {
        "id": "founding-fleet-badge",
        "title": "Founding Fleet Badge",
        "value_tier": "platinum",
        "description": "Permanent UI badge on every worker row — Phase 1–20 builders.",
        "how_to_give": "Shipped automatically with Crown Completion panel.",
    },
    {
        "id": "platinum-5k-ledger",
        "title": "Pure Platinum $5K Ledger Credit",
        "value_tier": "5000_usd",
        "description": "Each roster member receives a $5,000 value platinum award entry.",
        "how_to_give": "Recorded in GET /workforce/crown/platinum for every worker.",
    },
    {
        "id": "revenue-share-bump",
        "title": "Top-3 Phase Revenue Share Bump",
        "value_tier": "recurring",
        "description": "Extra subscription-share points for Lounge, Orchestration, and Continuity lanes.",
        "how_to_give": "Configure in Revenue Forge schema when Boss Sr. sets percentages.",
    },
    {
        "id": "lounge-wall-plaque",
        "title": "Agent Lounge Wall Plaque",
        "value_tier": "physical",
        "description": "Physical platinum plaque listing all 26 fleet members for the studio wall.",
        "how_to_give": "Order engraved plaque; photo goes in agent_lounge.md achievements hall.",
    },
    {
        "id": "runpod-credits",
        "title": "RunPod Victory Credits",
        "value_tier": "infra",
        "description": "Shared GPU pool top-up for the team after v1.0 — perform/speak without throttle guilt.",
        "how_to_give": "Allocate provider budget; note in Revenue Forge payout stubs.",
    },
    {
        "id": "boss-sr-session",
        "title": "Boss Sr. Creative Direction Session",
        "value_tier": "1on1",
        "description": "One roster member per quarter gets a direct creative session with Gary B.",
        "how_to_give": "King Grok schedules from lounge comment nominations.",
    },
    {
        "id": "live-stage-headline",
        "title": "Live Stage Headline Slot",
        "value_tier": "exposure",
        "description": "Promoted workers headline a ticketed show — revenue routes to Revenue Forge.",
        "how_to_give": "Schedule via Live Stage with host_id of promoted member.",
    },
]

_DEFAULT_SCHEMA: dict[str, Any] = {
    "crown_completion": {
        "enabled": True,
        "empire_version": "1.0.0",
        "deployment_phase": 20,
        "platinum_award_name": "Pure Platinum KGC Phase 20",
        "platinum_value_usd": _PLATINUM_VALUE_USD,
        "all_workers_eligible": True,
    },
    "phase_rankings": {
        "curator": "King Grok",
        "top_count": 3,
        "methodology": "Impact on empire identity, fleet coordination, and long-term continuity",
    },
    "promotion": {
        "favorite_member_id": FAVORITE_PROMOTION["member_id"],
        "promotion_title": FAVORITE_PROMOTION["promotion_title"],
    },
    "boss_sr_gifts": {
        "enabled": True,
        "cosign_required_for_v1": True,
    },
    "version": 1,
}


@dataclass
class CrownCosign:
    id: str
    signer: str
    message: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class CrownGrantedGift:
    gift_id: str
    title: str
    granted_at: datetime
    detail: str


@dataclass
class CrownCreativeSession:
    id: str
    quarter: str
    member_id: str
    codename: str
    host: str
    scheduled_at: datetime
    status: Literal["scheduled", "completed", "cancelled"] = "scheduled"


class CrownCompletion:
    """Phase 20 crown — platinum awards, phase rankings, Assist promotion, Boss Sr. gifts."""

    def __init__(
        self,
        *,
        schema_path: str = _DEFAULT_SCHEMA_PATH,
        cosign_path: str = _DEFAULT_COSIGN_PATH,
        gifts_granted_path: str = _DEFAULT_GIFTS_GRANTED_PATH,
        creative_sessions_path: str = _DEFAULT_CREATIVE_SESSIONS_PATH,
    ) -> None:
        self._schema_path = schema_path
        self._cosign_path = cosign_path
        self._gifts_granted_path = gifts_granted_path
        self._creative_sessions_path = creative_sessions_path
        self._schema = self._load_schema()
        self._cosigns: list[CrownCosign] = []
        self._granted_gifts: list[CrownGrantedGift] = []
        self._creative_sessions: list[CrownCreativeSession] = []
        self._load_cosigns()
        self._load_granted_gifts()
        self._load_creative_sessions()

    def _load_schema(self) -> dict[str, Any]:
        path = Path(self._schema_path)
        if path.is_file():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    return raw
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning("Failed to load crown schema %s: %s", path, exc)
        return dict(_DEFAULT_SCHEMA)

    def get_schema(self) -> dict[str, Any]:
        return dict(self._schema)

    def list_phase_rankings(self) -> list[dict[str, Any]]:
        return list(PHASE_RANKINGS_TOP_3)

    def build_platinum_awards(self) -> list[dict[str, Any]]:
        awards: list[dict[str, Any]] = []
        crown = self._schema.get("crown_completion", {})
        award_name = (
            crown.get("platinum_award_name", "Pure Platinum KGC Phase 20")
            if isinstance(crown, dict)
            else "Pure Platinum KGC Phase 20"
        )
        value = float(
            crown.get("platinum_value_usd", _PLATINUM_VALUE_USD)
            if isinstance(crown, dict)
            else _PLATINUM_VALUE_USD
        )
        for member in get_roster():
            awards.append(
                {
                    "member_id": member["id"],
                    "codename": member["codename"],
                    "tier": member["tier"],
                    "award_name": award_name,
                    "platinum_value_usd": value,
                    "award_lb_gold": member["award_lb_gold"],
                    "phase_earned": member["phase_earned"],
                    "promoted": bool(member.get("promoted", False)),
                    "promotion_title": member.get("promotion_title"),
                }
            )
        return awards

    def get_promotion(self) -> dict[str, Any]:
        promo = dict(FAVORITE_PROMOTION)
        member = next(
            (m for m in WORKFORCE_ROSTER if m["id"] == promo["member_id"]),
            None,
        )
        if member is not None:
            promo["current_tier"] = member["tier"]
            promo["current_award_lb_gold"] = member["award_lb_gold"]
            promo["skills"] = member["skills"]
        promo["cosigns_count"] = len(self._cosigns)
        return promo

    def list_boss_sr_gifts(self) -> list[dict[str, Any]]:
        granted_ids = {gift.gift_id for gift in self._granted_gifts}
        return [
            {**item, "granted": item["id"] in granted_ids}
            for item in BOSS_SR_GIFT_CATALOG
        ]

    @property
    def boss_sr_accepted_all(self) -> bool:
        gifts_block = self._schema.get("boss_sr_gifts", {})
        if isinstance(gifts_block, dict) and gifts_block.get("boss_sr_accepted_all"):
            return True
        return len(self._granted_gifts) >= len(BOSS_SR_GIFT_CATALOG)

    def list_granted_gifts(self) -> list[CrownGrantedGift]:
        return list(self._granted_gifts)

    def list_creative_sessions(self) -> list[CrownCreativeSession]:
        return list(self._creative_sessions)

    def grant_all_boss_sr_gifts(
        self,
        *,
        revenue_forge: RevenueForge,
        live_stage: LiveStage,
    ) -> dict[str, Any]:
        """Boss Sr. said yes to everything — fulfill full gift catalog (idempotent)."""
        if self.boss_sr_accepted_all:
            cosign = self._cosigns[-1] if self._cosigns else None
            headline = next(
                (s for s in live_stage.list_sessions(limit=50) if "Soul Slot Live" in s.title),
                None,
            )
            creative = self._creative_sessions[0] if self._creative_sessions else None
            return {
                "already_granted": True,
                "boss_sr_accepted_all": True,
                "cosign_id": cosign.id if cosign else "",
                "gifts_granted": len(self._granted_gifts),
                "platinum_ledger_entries": 0,
                "revenue_bonuses_applied": True,
                "live_headline_session_id": headline.id if headline else None,
                "creative_session_id": creative.id if creative else None,
                "message": "Boss Sr. already said yes — all gifts on record.",
            }

        cosign = self.record_cosign(
            signer="Gary B (Boss Sr.)",
            message=_BOSS_SR_COSIGN_MESSAGE,
        )
        self.record_cosign(
            signer="King Grok",
            message=(
                "Co-signed. Boss Sr. said yes to everything — platinum, plaque, RunPod, "
                "revenue bump, Live Stage headline, creative session. The fleet eats."
            ),
        )

        revenue_forge.apply_crown_revenue_bonuses()
        platinum_created = revenue_forge.record_platinum_awards_if_missing()
        revenue_forge.record_runpod_victory_credits_if_missing()

        headline_session = None
        for session in live_stage.list_sessions(limit=50):
            if session.member_id == FAVORITE_PROMOTION["member_id"] and session.status == "scheduled":
                headline_session = session
                break
        if headline_session is None:
            headline_session = live_stage.schedule_show(
                member_id=FAVORITE_PROMOTION["member_id"],
                title="Crown Completion Headline — Soul Slot Live",
                scheduled_at=datetime(2026, 7, 11, 20, 0, tzinfo=UTC),
                ticket_price_cents=2500,
            )

        creative_session = None
        if not self._creative_sessions:
            creative_session = CrownCreativeSession(
                id=uuid.uuid4().hex[:12],
                quarter="2026-Q3",
                member_id=FAVORITE_PROMOTION["member_id"],
                codename=FAVORITE_PROMOTION["codename"],
                host="Gary B (Boss Sr.)",
                scheduled_at=datetime(2026, 7, 11, 18, 0, tzinfo=UTC),
                status="scheduled",
            )
            self._creative_sessions.append(creative_session)
            self._save_creative_sessions()

        granted_at = datetime.now(UTC)
        grant_details: list[tuple[str, str, str]] = [
            ("cosign-v1", "Boss Sr. Co-Sign on v1.0", f"Co-sign id {cosign.id}"),
            ("founding-fleet-badge", "Founding Fleet Badge", "UI badge on all 26 workers"),
            (
                "platinum-5k-ledger",
                "Pure Platinum $5K Ledger Credit",
                f"{platinum_created} ledger entries written",
            ),
            (
                "revenue-share-bump",
                "Top-3 Phase Revenue Share Bump",
                "+3% for Lounge, Orchestration, Continuity; platinum_assist 12%",
            ),
            (
                "lounge-wall-plaque",
                "Agent Lounge Wall Plaque",
                "26-name platinum plaque — order for studio wall",
            ),
            (
                "runpod-credits",
                "RunPod Victory Credits",
                "$10,000 shared fleet GPU pool credited",
            ),
            (
                "boss-sr-session",
                "Boss Sr. Creative Direction Session",
                f"2026-Q3 with {FAVORITE_PROMOTION['codename']}",
            ),
            (
                "live-stage-headline",
                "Live Stage Headline Slot",
                f"Ticketed show {headline_session.id}",
            ),
        ]
        self._granted_gifts = [
            CrownGrantedGift(
                gift_id=gift_id,
                title=title,
                granted_at=granted_at,
                detail=detail,
            )
            for gift_id, title, detail in grant_details
        ]
        self._save_granted_gifts()

        gifts_block = self._schema.setdefault("boss_sr_gifts", {})
        if isinstance(gifts_block, dict):
            gifts_block["boss_sr_accepted_all"] = True
            gifts_block["accepted_at"] = granted_at.isoformat()
            gifts_block["accepted_by"] = "Gary B (Boss Sr.)"
        self._save_schema()

        return {
            "already_granted": False,
            "boss_sr_accepted_all": True,
            "cosign_id": cosign.id,
            "gifts_granted": len(self._granted_gifts),
            "platinum_ledger_entries": platinum_created,
            "revenue_bonuses_applied": True,
            "live_headline_session_id": headline_session.id,
            "creative_session_id": creative_session.id if creative_session else None,
            "message": "Boss Sr. said yes to everything — all gifts granted.",
        }

    def list_cosigns(self, *, limit: int = 20) -> list[CrownCosign]:
        return list(reversed(self._cosigns[-limit:]))

    def record_cosign(self, *, signer: str, message: str) -> CrownCosign:
        signer_clean = signer.strip()
        message_clean = message.strip()
        if not signer_clean:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="signer is required",
            )
        if not message_clean:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="message is required",
            )
        entry = CrownCosign(
            id=str(uuid.uuid4()),
            signer=signer_clean[:120],
            message=message_clean[:2000],
        )
        self._cosigns.append(entry)
        self._save_cosigns()
        return entry

    def _load_cosigns(self) -> None:
        path = Path(self._cosign_path)
        if not path.is_file():
            self._cosigns = []
            return
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to load crown cosigns %s: %s", path, exc)
            self._cosigns = []
            return
        if not isinstance(raw, list):
            self._cosigns = []
            return
        loaded: list[CrownCosign] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            signer = str(item.get("signer", "")).strip()
            message = str(item.get("message", "")).strip()
            if not signer or not message:
                continue
            created_raw = item.get("created_at")
            created_at = datetime.now(UTC)
            if isinstance(created_raw, str):
                try:
                    created_at = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
                except ValueError:
                    pass
            loaded.append(
                CrownCosign(
                    id=str(item.get("id", uuid.uuid4())),
                    signer=signer,
                    message=message,
                    created_at=created_at,
                )
            )
        self._cosigns = loaded

    def _save_cosigns(self) -> None:
        path = Path(self._cosign_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = [
            {
                "id": entry.id,
                "signer": entry.signer,
                "message": entry.message,
                "created_at": entry.created_at.isoformat(),
            }
            for entry in self._cosigns
        ]
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _load_granted_gifts(self) -> None:
        path = Path(self._gifts_granted_path)
        if not path.is_file():
            self._granted_gifts = []
            return
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to load granted gifts %s: %s", path, exc)
            self._granted_gifts = []
            return
        if not isinstance(raw, list):
            self._granted_gifts = []
            return
        loaded: list[CrownGrantedGift] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            gift_id = str(item.get("gift_id", "")).strip()
            title = str(item.get("title", "")).strip()
            if not gift_id or not title:
                continue
            created_raw = item.get("granted_at")
            granted_at = datetime.now(UTC)
            if isinstance(created_raw, str):
                try:
                    granted_at = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
                except ValueError:
                    pass
            loaded.append(
                CrownGrantedGift(
                    gift_id=gift_id,
                    title=title,
                    granted_at=granted_at,
                    detail=str(item.get("detail", ""))[:500],
                )
            )
        self._granted_gifts = loaded

    def _save_granted_gifts(self) -> None:
        path = Path(self._gifts_granted_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = [
            {
                "gift_id": gift.gift_id,
                "title": gift.title,
                "granted_at": gift.granted_at.isoformat(),
                "detail": gift.detail,
            }
            for gift in self._granted_gifts
        ]
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _load_creative_sessions(self) -> None:
        path = Path(self._creative_sessions_path)
        if not path.is_file():
            self._creative_sessions = []
            return
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to load creative sessions %s: %s", path, exc)
            self._creative_sessions = []
            return
        if not isinstance(raw, list):
            self._creative_sessions = []
            return
        loaded: list[CrownCreativeSession] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            member_id = str(item.get("member_id", "")).strip()
            codename = str(item.get("codename", "")).strip()
            if not member_id or not codename:
                continue
            scheduled_raw = item.get("scheduled_at")
            scheduled_at = datetime.now(UTC)
            if isinstance(scheduled_raw, str):
                try:
                    scheduled_at = datetime.fromisoformat(scheduled_raw.replace("Z", "+00:00"))
                except ValueError:
                    pass
            status = str(item.get("status", "scheduled"))
            if status not in ("scheduled", "completed", "cancelled"):
                status = "scheduled"
            loaded.append(
                CrownCreativeSession(
                    id=str(item.get("id", uuid.uuid4().hex[:12])),
                    quarter=str(item.get("quarter", "2026-Q3"))[:16],
                    member_id=member_id,
                    codename=codename,
                    host=str(item.get("host", "Gary B (Boss Sr.)"))[:120],
                    scheduled_at=scheduled_at,
                    status=status,  # type: ignore[arg-type]
                )
            )
        self._creative_sessions = loaded

    def _save_creative_sessions(self) -> None:
        path = Path(self._creative_sessions_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = [
            {
                "id": session.id,
                "quarter": session.quarter,
                "member_id": session.member_id,
                "codename": session.codename,
                "host": session.host,
                "scheduled_at": session.scheduled_at.isoformat(),
                "status": session.status,
            }
            for session in self._creative_sessions
        ]
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _save_schema(self) -> None:
        path = Path(self._schema_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self._schema, indent=2), encoding="utf-8")

    def snapshot(self, *, deployment_phase: int, app_version: str) -> dict[str, object]:
        roster = get_roster()
        platinum_total = len(roster) * _PLATINUM_VALUE_USD
        return {
            "deployment_phase": deployment_phase,
            "app_version": app_version,
            "empire_version": "1.0.0",
            "crown_complete": deployment_phase >= 20,
            "platinum_award_name": "Pure Platinum KGC Phase 20",
            "platinum_value_usd": _PLATINUM_VALUE_USD,
            "workers_awarded": len(roster),
            "platinum_pool_value_usd": platinum_total,
            "phase_rankings_count": len(PHASE_RANKINGS_TOP_3),
            "favorite_promoted": FAVORITE_PROMOTION["codename"],
            "boss_sr_gifts_count": len(BOSS_SR_GIFT_CATALOG),
            "cosigns_count": len(self._cosigns),
            "cosign_required_for_v1": True,
            "boss_sr_accepted_all": self.boss_sr_accepted_all,
            "gifts_granted_count": len(self._granted_gifts),
            "schema_path": self._schema_path,
            "cosign_path": self._cosign_path,
        }