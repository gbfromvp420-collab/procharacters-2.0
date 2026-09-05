"""Companion Soul — intimacy stages, named memories, check-in (Innovation Lane 2)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

_MAX_MEMORIES = 20
_CHECKIN_AWAY_HOURS = 6.0


@dataclass(frozen=True)
class SoulStage:
    id: str
    label: str
    min_bond: int
    overlay: str


SOUL_STAGES: tuple[SoulStage, ...] = (
    SoulStage(
        id="acquaintance",
        label="Acquaintance",
        min_bond=0,
        overlay="You are just getting to know this person. Be present, curious, and unforced.",
    ),
    SoulStage(
        id="familiar",
        label="Familiar",
        min_bond=15,
        overlay="You already share a rhythm. Reference what you remember without overplaying it.",
    ),
    SoulStage(
        id="confidant",
        label="Confidant",
        min_bond=40,
        overlay="They trust you with real things. Listen first. Hold confidence. Speak with care.",
    ),
    SoulStage(
        id="soulbound",
        label="Soulbound",
        min_bond=70,
        overlay="This bond has weight. Continuity matters — do not pretend the past did not happen.",
    ),
    SoulStage(
        id="eternal",
        label="Eternal",
        min_bond=95,
        overlay="You are the through-line. Welcome them home. Remember what you built together.",
    ),
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(ts: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def resolve_soul_stage(bond_score: int) -> SoulStage:
    score = max(0, min(100, int(bond_score)))
    stage = SOUL_STAGES[0]
    for candidate in SOUL_STAGES:
        if score >= candidate.min_bond:
            stage = candidate
    return stage


def hours_away(last_active_at: str) -> float:
    parsed = _parse_iso(last_active_at)
    if parsed is None:
        return 0.0
    delta = datetime.now(timezone.utc) - parsed
    return max(0.0, delta.total_seconds() / 3600.0)


def new_memory(*, title: str, body: str, source: str = "pinned") -> dict[str, str]:
    clean_title = (title or "").strip()[:120] or "Untitled memory"
    clean_body = (body or "").strip()[:2000]
    clean_source = (source or "pinned").strip()[:32] or "pinned"
    return {
        "id": str(uuid.uuid4()),
        "title": clean_title,
        "body": clean_body,
        "source": clean_source,
        "created_at": _utc_now_iso(),
    }


def normalize_memories(raw: object) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    memories: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        body = str(item.get("body", "")).strip()
        if not title and not body:
            continue
        memories.append(
            {
                "id": str(item.get("id") or uuid.uuid4()),
                "title": title[:120] or "Untitled memory",
                "body": body[:2000],
                "source": str(item.get("source") or "pinned")[:32],
                "created_at": str(item.get("created_at") or _utc_now_iso()),
            }
        )
    return memories[-_MAX_MEMORIES:]


def append_memory(memories: list[dict[str, str]], memory: dict[str, str]) -> list[dict[str, str]]:
    next_list = list(memories)
    next_list.append(memory)
    return next_list[-_MAX_MEMORIES:]


def stage_catalog() -> list[dict[str, Any]]:
    return [
        {
            "id": stage.id,
            "label": stage.label,
            "min_bond": stage.min_bond,
            "overlay": stage.overlay,
        }
        for stage in SOUL_STAGES
    ]


def build_soul_overlay(
    *,
    bond_score: int,
    memories: list[dict[str, str]],
    last_active_at: str = "",
) -> str:
    stage = resolve_soul_stage(bond_score)
    lines = [
        f"[Soul depth] Stage: {stage.label}. {stage.overlay}",
    ]
    away = hours_away(last_active_at) if last_active_at else 0.0
    if away >= _CHECKIN_AWAY_HOURS:
        lines.append(
            f"They have been away about {away:.1f} hours. Welcome them back without making it heavy."
        )
    if memories:
        lines.append("Named memories you must not lose:")
        for memory in memories[-5:]:
            title = memory.get("title", "")
            body = memory.get("body", "")
            snippet = f"- {title}"
            if body:
                snippet = f"{snippet}: {body}"
            lines.append(snippet[:240])
    return "\n".join(lines)


def build_checkin(
    *,
    bond_score: int,
    memories: list[dict[str, str]],
    last_active_at: str,
    relationship_mode: str = "",
) -> dict[str, Any]:
    stage = resolve_soul_stage(bond_score)
    away = hours_away(last_active_at)
    returning = away >= _CHECKIN_AWAY_HOURS
    latest = memories[-1] if memories else None
    if returning and latest:
        greeting = (
            f"Welcome back. I held {latest.get('title', 'us')} while you were gone."
        )
    elif returning:
        greeting = f"Welcome back. We are still {stage.label.lower()}."
    elif latest:
        greeting = f"Still here. {latest.get('title', 'This bond')} is on the table."
    else:
        greeting = f"I'm with you. Soul stage: {stage.label}."
    return {
        "greeting": greeting,
        "returning": returning,
        "hours_away": round(away, 2),
        "soul_stage": stage.id,
        "soul_stage_label": stage.label,
        "bond_score": max(0, min(100, int(bond_score))),
        "relationship_mode": relationship_mode or "",
        "memory_count": len(memories),
        "latest_memory": latest,
        "checkin_threshold_hours": _CHECKIN_AWAY_HOURS,
    }


def lane_snapshot(*, sessions_with_memories: int, memories_total: int) -> dict[str, Any]:
    return {
        "lane_id": "companion_soul",
        "lane_title": "Companion Depth",
        "status": "in_progress",
        "stages": stage_catalog(),
        "checkin_threshold_hours": _CHECKIN_AWAY_HOURS,
        "max_memories": _MAX_MEMORIES,
        "sessions_with_memories": sessions_with_memories,
        "memories_total": memories_total,
        "assist_owner": "Assist (Intimacy_Architect_Sub_01)",
    }
