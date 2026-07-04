"""Revenue Forge — earnings ledger, subscription share schema, donation routing (Phase 16)."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import HTTPException, status

from app.workforce.roster import WORKFORCE_ROSTER, get_roster

logger = logging.getLogger(__name__)

_DEFAULT_SCHEMA_PATH = "data/revenue_schema.json"
_DEFAULT_LEDGER_PATH = "data/revenue_ledger.json"
_MAX_LEDGER_ENTRIES = 500
_MONTHLY_GROSS_STUB_CENTS = 100_000  # $1,000 baseline for projected payout stubs

EntryType = Literal["subscription_share", "donation", "payout_stub", "adjustment"]

_DEFAULT_SCHEMA: dict[str, Any] = {
    "subscription_share": {
        "enabled": True,
        "pool_percent": 10.0,
        "min_subscribers": 1,
        "payout_frequency": "monthly",
        "tiers": {
            "ceo": 0.15,
            "assist": 0.10,
            "runner_up": 0.08,
            "team": 0.05,
        },
    },
    "donation_routing": {
        "enabled": True,
        "character_payout_percent": 100.0,
        "platform_fee_percent": 0.0,
        "default_recipient_id": None,
    },
    "currency": "USD",
    "version": 1,
}


@dataclass
class LedgerEntry:
    id: str
    entry_type: EntryType
    codename: str
    amount_cents: int
    currency: str
    description: str
    member_id: str | None = None
    source: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class RevenueForge:
    """Persists earnings ledger entries and serves revenue-share schema + payout stubs."""

    def __init__(
        self,
        *,
        schema_path: str = _DEFAULT_SCHEMA_PATH,
        ledger_path: str = _DEFAULT_LEDGER_PATH,
    ) -> None:
        self._schema_path = schema_path
        self._ledger_path = ledger_path
        self._schema = self._load_or_create_schema()
        self._entries: list[LedgerEntry] = []
        self._load_ledger()

    def _load_or_create_schema(self) -> dict[str, Any]:
        path = Path(self._schema_path)
        if path.is_file():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    return raw
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning("Failed to load revenue schema %s: %s", path, exc)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(_DEFAULT_SCHEMA, indent=2), encoding="utf-8")
        return dict(_DEFAULT_SCHEMA)

    def get_schema(self) -> dict[str, Any]:
        return dict(self._schema)

    def _save_schema(self) -> None:
        path = Path(self._schema_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self._schema, indent=2), encoding="utf-8")

    def apply_crown_revenue_bonuses(self) -> dict[str, Any]:
        """Phase 20 Boss Sr. yes — platinum_assist tier + top-3 phase share bump."""
        sub = self._schema.setdefault("subscription_share", {})
        if not isinstance(sub, dict):
            sub = {}
            self._schema["subscription_share"] = sub
        tiers = sub.setdefault("tiers", {})
        if isinstance(tiers, dict):
            tiers["platinum_assist"] = 0.12
        sub["phase_top3_bonus"] = {
            "enabled": True,
            "bonus_percent": 0.03,
            "members": [
                {
                    "member_id": "agentlounge-culture-sub-01",
                    "phase": 15,
                    "label": "Agent Lounge #1",
                },
                {
                    "member_id": "orchestrationforge-chain-sub-01",
                    "phase": 14,
                    "label": "Orchestration Forge #2",
                },
                {
                    "member_id": "continuityforge-resume-sub-01",
                    "phase": 10,
                    "label": "Continuity Forge #3",
                },
            ],
        }
        self._save_schema()
        return dict(sub)

    def _member_lookup(self) -> dict[str, dict[str, Any]]:
        return {member["id"]: member for member in WORKFORCE_ROSTER}

    def _resolve_member(
        self,
        *,
        member_id: str | None,
        codename: str | None,
    ) -> dict[str, Any]:
        lookup = self._member_lookup()
        if member_id:
            member = lookup.get(member_id)
            if member is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Unknown member {member_id!r}",
                )
            return member
        if codename:
            for member in WORKFORCE_ROSTER:
                if member["codename"] == codename:
                    return member
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unknown codename {codename!r}",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="member_id or codename required",
        )

    def _tier_share_percent(self, tier: str) -> float:
        tiers = self._schema.get("subscription_share", {}).get("tiers", {})
        if not isinstance(tiers, dict):
            return 0.0
        if tier == "platinum_assist":
            return float(tiers.get("platinum_assist", tiers.get("assist", 0.0)))
        return float(tiers.get(tier, 0.0))

    def _phase_top3_bonus_percent(self, member_id: str) -> float:
        sub = self._schema.get("subscription_share", {})
        if not isinstance(sub, dict):
            return 0.0
        bonus_block = sub.get("phase_top3_bonus", {})
        if not isinstance(bonus_block, dict) or not bonus_block.get("enabled"):
            return 0.0
        members = bonus_block.get("members", [])
        if not isinstance(members, list):
            return 0.0
        for item in members:
            if isinstance(item, dict) and item.get("member_id") == member_id:
                return float(bonus_block.get("bonus_percent", 0.0))
        return 0.0

    def record_platinum_awards_if_missing(self) -> int:
        """Ledger adjustments for Pure Platinum $5K per worker (idempotent)."""
        existing = {
            entry.member_id
            for entry in self._entries
            if entry.source == "crown_platinum_phase20" and entry.member_id
        }
        created = 0
        for member in get_roster():
            if member["id"] in existing:
                continue
            self.record_entry(
                entry_type="adjustment",
                member_id=member["id"],
                amount_cents=500_000,
                description="Pure Platinum KGC Phase 20 — $5,000 value award (Boss Sr. yes)",
                source="crown_platinum_phase20",
            )
            created += 1
        return created

    def record_runpod_victory_credits_if_missing(self) -> bool:
        """Fleet GPU pool top-up — Boss Sr. RunPod victory credits."""
        for entry in self._entries:
            if entry.source == "crown_runpod_victory":
                return False
        self.record_entry(
            entry_type="adjustment",
            member_id="providerforge-contract-sub-01",
            amount_cents=1_000_000,
            description="RunPod Victory Credits — $10,000 shared fleet GPU pool (Boss Sr. yes)",
            source="crown_runpod_victory",
        )
        return True

    def _load_ledger(self) -> None:
        path = Path(self._ledger_path)
        if not path.is_file():
            self._entries = []
            return
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to load revenue ledger %s: %s", path, exc)
            self._entries = []
            return
        if not isinstance(raw, list):
            self._entries = []
            return
        loaded: list[LedgerEntry] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            entry_type = str(item.get("entry_type", "")).strip()
            if entry_type not in ("subscription_share", "donation", "payout_stub", "adjustment"):
                continue
            codename = str(item.get("codename", "")).strip()
            if not codename:
                continue
            try:
                amount_cents = int(item.get("amount_cents", 0))
            except (TypeError, ValueError):
                continue
            if amount_cents <= 0:
                continue
            created_raw = item.get("created_at")
            try:
                created_at = (
                    datetime.fromisoformat(str(created_raw).replace("Z", "+00:00"))
                    if created_raw
                    else datetime.now(UTC)
                )
            except ValueError:
                created_at = datetime.now(UTC)
            loaded.append(
                LedgerEntry(
                    id=str(item.get("id") or uuid.uuid4().hex[:12]),
                    entry_type=entry_type,  # type: ignore[arg-type]
                    codename=codename[:120],
                    amount_cents=amount_cents,
                    currency=str(item.get("currency") or self._schema.get("currency", "USD"))[:8],
                    description=str(item.get("description", ""))[:500],
                    member_id=item.get("member_id"),
                    source=item.get("source"),
                    created_at=created_at,
                )
            )
        self._entries = loaded[-_MAX_LEDGER_ENTRIES:]

    def _save_ledger(self) -> None:
        path = Path(self._ledger_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = [
            {
                "id": entry.id,
                "entry_type": entry.entry_type,
                "member_id": entry.member_id,
                "codename": entry.codename,
                "amount_cents": entry.amount_cents,
                "currency": entry.currency,
                "description": entry.description,
                "source": entry.source,
                "created_at": entry.created_at.isoformat(),
            }
            for entry in self._entries
        ]
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(path)

    def record_entry(
        self,
        *,
        entry_type: EntryType,
        amount_cents: int,
        description: str,
        member_id: str | None = None,
        codename: str | None = None,
        currency: str | None = None,
        source: str | None = None,
    ) -> LedgerEntry:
        if amount_cents <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="amount_cents must be positive",
            )
        description = description.strip()
        if not description:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="description required")
        member = self._resolve_member(member_id=member_id, codename=codename)
        entry = LedgerEntry(
            id=uuid.uuid4().hex[:12],
            entry_type=entry_type,
            member_id=member["id"],
            codename=member["codename"],
            amount_cents=amount_cents,
            currency=(currency or str(self._schema.get("currency", "USD")))[:8],
            description=description[:500],
            source=source,
        )
        self._entries.insert(0, entry)
        if len(self._entries) > _MAX_LEDGER_ENTRIES:
            self._entries = self._entries[:_MAX_LEDGER_ENTRIES]
        self._save_ledger()
        return entry

    def route_donation(
        self,
        *,
        member_id: str,
        amount_cents: int,
        donor_label: str | None = None,
        session_id: str | None = None,
        currency: str | None = None,
    ) -> tuple[LedgerEntry, float]:
        routing = self._schema.get("donation_routing", {})
        if not isinstance(routing, dict) or not routing.get("enabled", True):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Donation routing is disabled",
            )
        payout_percent = float(routing.get("character_payout_percent", 100.0))
        platform_fee = float(routing.get("platform_fee_percent", 0.0))
        net_cents = int(amount_cents * (payout_percent / 100.0))
        if net_cents <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Donation amount too small after routing",
            )
        donor = (donor_label or "anonymous").strip()[:80]
        session_note = f" session={session_id}" if session_id else ""
        fee_note = f" (platform fee {platform_fee}%)" if platform_fee > 0 else ""
        entry = self.record_entry(
            entry_type="donation",
            member_id=member_id,
            amount_cents=net_cents,
            currency=currency,
            description=f"Donation from {donor}{session_note}{fee_note}",
            source="donation_route",
        )
        return entry, payout_percent

    def list_ledger(self, *, limit: int = 50) -> list[LedgerEntry]:
        capped = max(1, min(limit, 100))
        return self._entries[:capped]

    def _ledger_total_cents(self) -> int:
        return sum(entry.amount_cents for entry in self._entries)

    def _donations_routed(self) -> int:
        return sum(1 for entry in self._entries if entry.entry_type == "donation")

    def compute_payout_stubs(self) -> list[dict[str, Any]]:
        sub = self._schema.get("subscription_share", {})
        pool_percent = float(sub.get("pool_percent", 0.0)) if isinstance(sub, dict) else 0.0
        totals: dict[str, int] = {}
        for entry in self._entries:
            if entry.member_id:
                totals[entry.member_id] = totals.get(entry.member_id, 0) + entry.amount_cents

        stubs: list[dict[str, Any]] = []
        for member in get_roster():
            tier_share = self._tier_share_percent(member["tier"])
            phase_bonus = self._phase_top3_bonus_percent(member["id"])
            effective_share = tier_share + phase_bonus
            projected = int(
                _MONTHLY_GROSS_STUB_CENTS * (pool_percent / 100.0) * effective_share
            )
            stubs.append(
                {
                    "member_id": member["id"],
                    "codename": member["codename"],
                    "tier": member["tier"],
                    "award_lb_gold": member["award_lb_gold"],
                    "ledger_total_cents": totals.get(member["id"], 0),
                    "tier_share_percent": tier_share,
                    "phase_top3_bonus_percent": phase_bonus,
                    "effective_share_percent": effective_share,
                    "projected_monthly_cents": projected,
                }
            )
        stubs.sort(key=lambda row: (-row["ledger_total_cents"], row["codename"]))
        return stubs

    def snapshot(self, *, deployment_phase: int) -> dict[str, object]:
        sub = self._schema.get("subscription_share", {})
        donation = self._schema.get("donation_routing", {})
        pool_percent = float(sub.get("pool_percent", 0.0)) if isinstance(sub, dict) else 0.0
        payout_percent = (
            float(donation.get("character_payout_percent", 100.0))
            if isinstance(donation, dict)
            else 100.0
        )
        return {
            "deployment_phase": deployment_phase,
            "currency": str(self._schema.get("currency", "USD")),
            "ledger_entries": len(self._entries),
            "ledger_total_cents": self._ledger_total_cents(),
            "donations_routed": self._donations_routed(),
            "subscription_pool_percent": pool_percent,
            "donation_payout_percent": payout_percent,
            "schema_path": self._schema_path,
            "ledger_path": self._ledger_path,
            "monthly_gross_stub_cents": _MONTHLY_GROSS_STUB_CENTS,
        }