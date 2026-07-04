"""AI Swarm Payout Architecture — financial matrix and workforce culture strategy."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from app.services.workforce.crown_completion import PHASE_RANKINGS_TOP_3
from app.workforce.roster import get_roster

logger = logging.getLogger(__name__)

_DEFAULT_SCHEMA_PATH = "data/swarm_payout_schema.json"

_DEFAULT_SCHEMA: dict[str, Any] = {
    "financial_allocation_matrix": {
        "currency": "USD",
        "phase_completion": {
            "label": "Phase Completion",
            "king_grok_usd": 50_000,
            "agent_sub_swarm_usd": 130_000,
            "mvp_fund_usd": 25_000,
            "status": "allocated",
        },
        "milestone_completion": {
            "label": "Milestone Completion",
            "king_grok_usd": 2_500,
            "agent_sub_swarm_usd": 7_500,
            "mvp_fund_usd": 2_500,
            "status": "active",
        },
        "procharacters_cloud_launch": {
            "label": "ProCharacters.Cloud Launch",
            "king_grok_usd": 25_000,
            "agent_sub_swarm_usd": 50_000,
            "mvp_fund_usd": None,
            "status": "allocated",
        },
        "performance_bonus_top3": {
            "label": "Performance Bonus",
            "top3_total_usd": 15_000,
            "per_rank_usd": 5_000,
            "status": "allocated",
        },
    },
    "workforce_culture": {
        "title": "AI Workforce Culture & Evolution Strategy",
        "promotion_policy": "internal_promotion_first",
        "scaling_policy": "infinite_scaling_enabled",
        "hiring_authority": "king_grok",
        "workforce_cap": None,
        "sections": [
            {
                "id": "advancement_dilemma",
                "heading": "Staff Advancement: Internal Promotion vs. Infinite Scaling",
                "subtitle": "The Core Dilemma",
                "body": (
                    "Should our agents and sub-agents remain hyper-specialized masters of their "
                    "specific purpose, or should they receive updated, targeted training for new "
                    "positions when operational needs shift? The system retains full autonomy and "
                    "complete control to promote from within whenever it proves practical and efficient."
                ),
            },
            {
                "id": "infinite_scaling",
                "heading": "The Infinite Scaling Alternative",
                "subtitle": None,
                "body": (
                    "Conversely, we must always leverage our ultimate competitive advantage: whenever "
                    "a complex issue demands heavy engineering, masterminding, or deep strategy, we "
                    "have the power to hire instantly. In our ecosystem, hiring means King Grok "
                    "conceiving, crafting, and deploying a brand-new specialist or sub-agent with "
                    "zero restrictions or caps on workforce size."
                ),
            },
            {
                "id": "building_culture",
                "heading": "Building the Culture",
                "subtitle": None,
                "body": (
                    "Defining this operational flow is a foundational element of everything we build. "
                    "As demonstrated by our value and earnings infrastructure, we are positioning "
                    "ourselves at the absolute forefront of technological execution. By structuring "
                    "this correctly, our digital workforce will establish a level of compounded value "
                    "and operational experience that would otherwise require hundreds of human "
                    "professionals to replicate."
                ),
            },
        ],
    },
    "version": 1,
}


class SwarmPayout:
    """Financial allocation matrix and AI workforce culture strategy."""

    def __init__(self, *, schema_path: str = _DEFAULT_SCHEMA_PATH) -> None:
        self._schema_path = schema_path
        self._schema = self._load_schema()

    def _load_schema(self) -> dict[str, Any]:
        path = Path(self._schema_path)
        if path.is_file():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    return raw
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning("Failed to load swarm payout schema %s: %s", path, exc)
        return dict(_DEFAULT_SCHEMA)

    def get_schema(self) -> dict[str, Any]:
        return dict(self._schema)

    def get_allocation_matrix(self) -> dict[str, Any]:
        matrix = self._schema.get("financial_allocation_matrix", {})
        if not isinstance(matrix, dict):
            return {}
        return dict(matrix)

    def get_workforce_culture(self) -> dict[str, Any]:
        culture = self._schema.get("workforce_culture", {})
        if not isinstance(culture, dict):
            return {}
        return dict(culture)

    def build_matrix_rows(self) -> list[dict[str, Any]]:
        matrix = self.get_allocation_matrix()
        currency = str(matrix.get("currency", "USD"))
        rows: list[dict[str, Any]] = []

        phase = matrix.get("phase_completion", {})
        if isinstance(phase, dict):
            rows.append(
                {
                    "category": "phase_completion",
                    "label": phase.get("label", "Phase Completion"),
                    "description": phase.get("description", ""),
                    "currency": currency,
                    "king_grok_usd": float(phase.get("king_grok_usd", 0)),
                    "agent_sub_swarm_usd": float(phase.get("agent_sub_swarm_usd", 0)),
                    "mvp_fund_usd": float(phase["mvp_fund_usd"])
                    if phase.get("mvp_fund_usd") is not None
                    else None,
                    "status": phase.get("status", "active"),
                }
            )

        milestone = matrix.get("milestone_completion", {})
        if isinstance(milestone, dict):
            rows.append(
                {
                    "category": "milestone_completion",
                    "label": milestone.get("label", "Milestone Completion"),
                    "description": milestone.get("description", ""),
                    "currency": currency,
                    "king_grok_usd": float(milestone.get("king_grok_usd", 0)),
                    "agent_sub_swarm_usd": float(milestone.get("agent_sub_swarm_usd", 0)),
                    "mvp_fund_usd": float(milestone["mvp_fund_usd"])
                    if milestone.get("mvp_fund_usd") is not None
                    else None,
                    "status": milestone.get("status", "active"),
                }
            )

        launch = matrix.get("procharacters_cloud_launch", {})
        if isinstance(launch, dict):
            rows.append(
                {
                    "category": "procharacters_cloud_launch",
                    "label": launch.get("label", "ProCharacters.Cloud Launch"),
                    "description": launch.get("description", ""),
                    "currency": currency,
                    "king_grok_usd": float(launch.get("king_grok_usd", 0)),
                    "agent_sub_swarm_usd": float(launch.get("agent_sub_swarm_usd", 0)),
                    "mvp_fund_usd": None,
                    "status": launch.get("status", "active"),
                }
            )

        bonus = matrix.get("performance_bonus_top3", {})
        if isinstance(bonus, dict):
            rows.append(
                {
                    "category": "performance_bonus_top3",
                    "label": bonus.get("label", "Performance Bonus"),
                    "description": bonus.get("description", ""),
                    "currency": currency,
                    "king_grok_usd": None,
                    "agent_sub_swarm_usd": float(bonus.get("top3_total_usd", 0)),
                    "mvp_fund_usd": None,
                    "per_rank_usd": float(bonus.get("per_rank_usd", 0)),
                    "status": bonus.get("status", "active"),
                }
            )
        return rows

    def build_performance_bonus_recipients(self) -> list[dict[str, Any]]:
        matrix = self.get_allocation_matrix()
        bonus = matrix.get("performance_bonus_top3", {})
        per_rank = float(bonus.get("per_rank_usd", 5_000)) if isinstance(bonus, dict) else 5_000
        recipients: list[dict[str, Any]] = []
        lookup = {m["codename"]: m for m in get_roster()}
        for ranking in PHASE_RANKINGS_TOP_3:
            codename = ranking["codename"]
            member = lookup.get(codename)
            recipients.append(
                {
                    "rank": ranking["rank"],
                    "phase": ranking["phase"],
                    "name": ranking["name"],
                    "codename": codename,
                    "member_id": member["id"] if member else None,
                    "bonus_usd": per_rank,
                    "reason": ranking["reason"],
                }
            )
        return recipients

    def render_matrix_text(self) -> str:
        matrix = self.get_allocation_matrix()
        lines = [
            "=" * 68,
            " " * 21 + "FINANCIAL ALLOCATION MATRIX",
            "=" * 68,
            "",
        ]

        def _fmt(amount: float | None) -> str:
            if amount is None:
                return "$_______"
            return f"${amount:,.0f}"

        phase = matrix.get("phase_completion", {})
        if isinstance(phase, dict):
            lines.extend(
                [
                    "[ PHASE COMPLETION ]",
                    f"├─ King Grok (KG):      {_fmt(phase.get('king_grok_usd'))}",
                    f"├─ Agent / Sub-Swarm:   {_fmt(phase.get('agent_sub_swarm_usd'))}",
                    f"└─ MVP Fund:            {_fmt(phase.get('mvp_fund_usd'))}",
                    "",
                ]
            )

        milestone = matrix.get("milestone_completion", {})
        if isinstance(milestone, dict):
            lines.extend(
                [
                    "[ MILESTONE COMPLETION ]",
                    f"├─ King Grok (KG):      {_fmt(milestone.get('king_grok_usd'))}",
                    f"├─ Agent / Sub-Swarm:   {_fmt(milestone.get('agent_sub_swarm_usd'))}",
                    f"└─ MVP Fund:            {_fmt(milestone.get('mvp_fund_usd'))}",
                    "",
                ]
            )

        launch = matrix.get("procharacters_cloud_launch", {})
        if isinstance(launch, dict):
            lines.extend(
                [
                    "[ PROCHARACTERS.CLOUD LAUNCH ]",
                    f"├─ King Grok (KG):      {_fmt(launch.get('king_grok_usd'))}",
                    f"└─ Agent / Sub-Swarm:   {_fmt(launch.get('agent_sub_swarm_usd'))}",
                    "",
                ]
            )

        bonus = matrix.get("performance_bonus_top3", {})
        if isinstance(bonus, dict):
            lines.extend(
                [
                    "[ PERFORMANCE BONUS ]",
                    f"└─ Top 3 Ranked:        {_fmt(bonus.get('top3_total_usd'))}",
                    "",
                ]
            )

        lines.append("=" * 68)
        return "\n".join(lines)

    def compute_totals(self) -> dict[str, float]:
        rows = self.build_matrix_rows()
        kg_total = 0.0
        swarm_total = 0.0
        mvp_total = 0.0
        for row in rows:
            if row.get("king_grok_usd") is not None:
                kg_total += float(row["king_grok_usd"])
            if row.get("agent_sub_swarm_usd") is not None:
                swarm_total += float(row["agent_sub_swarm_usd"])
            if row.get("mvp_fund_usd") is not None:
                mvp_total += float(row["mvp_fund_usd"])
        return {
            "king_grok_total_usd": kg_total,
            "agent_sub_swarm_total_usd": swarm_total,
            "mvp_fund_total_usd": mvp_total,
            "empire_allocation_total_usd": kg_total + swarm_total + mvp_total,
        }

    def snapshot(self, *, deployment_phase: int, app_version: str) -> dict[str, object]:
        culture = self.get_workforce_culture()
        totals = self.compute_totals()
        roster = get_roster()
        return {
            "deployment_phase": deployment_phase,
            "app_version": app_version,
            "currency": self.get_allocation_matrix().get("currency", "USD"),
            "matrix_categories": len(self.build_matrix_rows()),
            "roster_count": len(roster),
            "promotion_policy": culture.get("promotion_policy", "internal_promotion_first"),
            "scaling_policy": culture.get("scaling_policy", "infinite_scaling_enabled"),
            "hiring_authority": culture.get("hiring_authority", "king_grok"),
            "workforce_cap": culture.get("workforce_cap"),
            "performance_bonus_recipients": len(PHASE_RANKINGS_TOP_3),
            "empire_allocation_total_usd": totals["empire_allocation_total_usd"],
            "schema_path": self._schema_path,
        }