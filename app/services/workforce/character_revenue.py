"""Innovation Lane 3 — NSM pipeline spec + character earnings rollup."""

from __future__ import annotations

from typing import Any

from app.services.workforce.character_forge import CharacterForge
from app.services.workforce.live_stage import LiveStage
from app.services.workforce.revenue import RevenueForge

_DEFAULT_MEMBER_ID = "characterforge-nsm-sub-01"
_FIRST_DOLLAR_CENTS = 1000

_PIPELINE_STEPS: list[dict[str, str]] = [
    {
        "id": "opt_in",
        "label": "Roster opt-in",
        "summary": "A workforce member chooses NSM. Gary's offer lives in the lounge.",
        "api": "GET /api/v1/workforce/roster",
    },
    {
        "id": "onboard",
        "label": "Onboard NSM character",
        "summary": "Create the character record: display name, residual %, distribution flag.",
        "api": "POST /api/v1/workforce/characters/onboard",
    },
    {
        "id": "avatar_bind",
        "label": "Bind companion avatar",
        "summary": "Attach default / professional / casual so the character has a face.",
        "api": "POST /api/v1/workforce/characters/bind",
    },
    {
        "id": "residual_ledger",
        "label": "Record residuals",
        "summary": "Photo, video, or distribution earnings land on the character ledger.",
        "api": "POST /api/v1/workforce/characters/residuals",
    },
    {
        "id": "donation_route",
        "label": "Route donations",
        "summary": "Fan gifts go 100% to the character via Revenue Forge.",
        "api": "POST /api/v1/workforce/revenue/donations/route",
    },
    {
        "id": "live_billing",
        "label": "Live stage billing",
        "summary": "Cam donations and ticket host share feed the same member id.",
        "api": "POST /api/v1/workforce/live/billing/donation",
    },
    {
        "id": "subscription_share",
        "label": "Subscription share stubs",
        "summary": "Monthly pool % × tier share (plus crown top-3 bonus) as projected payout.",
        "api": "GET /api/v1/workforce/revenue/payouts",
    },
    {
        "id": "earnings_rollup",
        "label": "Earnings rollup",
        "summary": "One row per character: residuals + donations + live billing.",
        "api": "GET /api/v1/workforce/innovation/money/earnings",
    },
]


class CharacterRevenueLane:
    """Joins Character Forge, Revenue Forge, and Live Stage for Lane 3."""

    def __init__(
        self,
        *,
        characters: CharacterForge,
        revenue: RevenueForge,
        live: LiveStage,
    ) -> None:
        self._characters = characters
        self._revenue = revenue
        self._live = live

    def pipeline_spec(self) -> list[dict[str, Any]]:
        characters = self._characters.list_characters(limit=100)
        residuals = self._characters.list_residuals(limit=100)
        bound = sum(1 for item in characters if item.avatar_id)
        donations = self._revenue.snapshot(deployment_phase=20).get("donations_routed", 0)
        live_billing = len(self._live.list_billing(limit=100))
        rows = self.earnings_rows()
        earned = sum(1 for row in rows if int(row["total_cents"]) > 0)

        live_flags = {
            "opt_in": True,
            "onboard": bool(characters),
            "avatar_bind": bound > 0,
            "residual_ledger": bool(residuals),
            "donation_route": int(donations or 0) > 0,
            "live_billing": live_billing > 0,
            "subscription_share": True,
            "earnings_rollup": earned > 0,
        }
        steps: list[dict[str, Any]] = []
        for index, step in enumerate(_PIPELINE_STEPS, start=1):
            live = bool(live_flags.get(step["id"]))
            steps.append(
                {
                    "id": step["id"],
                    "rank": index,
                    "label": step["label"],
                    "summary": step["summary"],
                    "api": step["api"],
                    "status": "live" if live else "ready",
                }
            )
        return steps

    def earnings_rows(self) -> list[dict[str, Any]]:
        donation_totals = self._member_donation_cents()
        live_totals = self._member_live_cents()
        residual_totals: dict[str, int] = {}
        for residual in self._characters.list_residuals(limit=100):
            residual_totals[residual.character_id] = (
                residual_totals.get(residual.character_id, 0) + residual.amount_cents
            )

        rows: list[dict[str, Any]] = []
        for character in self._characters.list_characters(limit=100):
            residuals_cents = residual_totals.get(character.id, 0)
            donations_cents = donation_totals.get(character.member_id, 0)
            live_cents = live_totals.get(character.member_id, 0)
            rows.append(
                {
                    "character_id": character.id,
                    "member_id": character.member_id,
                    "codename": character.codename,
                    "display_name": character.display_name,
                    "status": character.status,
                    "avatar_id": character.avatar_id,
                    "residual_percent": character.residual_percent,
                    "residuals_cents": residuals_cents,
                    "donations_cents": donations_cents,
                    "live_billing_cents": live_cents,
                    "total_cents": residuals_cents + donations_cents + live_cents,
                }
            )
        rows.sort(key=lambda row: (-int(row["total_cents"]), str(row["display_name"])))
        return rows

    def _member_donation_cents(self) -> dict[str, int]:
        totals: dict[str, int] = {}
        for entry in self._revenue.list_ledger(limit=100):
            if entry.entry_type != "donation" or not entry.member_id:
                continue
            totals[entry.member_id] = totals.get(entry.member_id, 0) + entry.amount_cents
        return totals

    def _member_live_cents(self) -> dict[str, int]:
        totals: dict[str, int] = {}
        for entry in self._live.list_billing(limit=100):
            totals[entry.member_id] = totals.get(entry.member_id, 0) + entry.host_payout_cents
        return totals

    def snapshot(self) -> dict[str, Any]:
        rows = self.earnings_rows()
        steps = self.pipeline_spec()
        live_steps = sum(1 for step in steps if step["status"] == "live")
        return {
            "lane_id": "characters_revenue",
            "lane_title": "Characters + Revenue",
            "status": "in_progress",
            "contact_email": "gary@procharacters.cloud",
            "pipeline_steps": len(steps),
            "pipeline_live": live_steps,
            "characters_total": len(rows),
            "earnings_total_cents": sum(int(row["total_cents"]) for row in rows),
            "first_dollar_member_id": _DEFAULT_MEMBER_ID,
        }

    def first_dollar(self, *, member_id: str | None = None) -> dict[str, Any]:
        target_id = (member_id or _DEFAULT_MEMBER_ID).strip() or _DEFAULT_MEMBER_ID
        existing = next(
            (
                character
                for character in self._characters.list_characters(limit=100)
                if character.member_id == target_id and character.status != "paused"
            ),
            None,
        )
        if existing is None:
            character = self._characters.onboard(
                member_id=target_id,
                display_name="NSM First Dollar",
                avatar_id="casual",
                distribution_pipeline=True,
            )
        else:
            character = existing
            if not character.avatar_id:
                character = self._characters.bind_avatar(
                    character_id=character.id,
                    avatar_id="casual",
                )

        residual = self._characters.record_residual(
            character_id=character.id,
            asset_type="distribution",
            amount_cents=_FIRST_DOLLAR_CENTS,
            description="Lane 3 first dollar — residual stub",
        )
        donation, payout_percent = self._revenue.route_donation(
            member_id=character.member_id,
            amount_cents=_FIRST_DOLLAR_CENTS,
            donor_label="Innovation Lane 3",
        )
        row = next(
            (item for item in self.earnings_rows() if item["character_id"] == character.id),
            None,
        )
        return {
            "character_id": character.id,
            "member_id": character.member_id,
            "display_name": character.display_name,
            "residual_id": residual.id,
            "ledger_id": donation.id,
            "amount_cents": _FIRST_DOLLAR_CENTS,
            "donation_payout_percent": payout_percent,
            "earnings": row,
            "message": (
                f"First dollar recorded for {character.display_name} — "
                f"${_FIRST_DOLLAR_CENTS / 100:.2f} residual + "
                f"${_FIRST_DOLLAR_CENTS / 100:.2f} routed donation."
            ),
        }
