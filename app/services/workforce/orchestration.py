"""Orchestration Forge — task chains and parent→child dispatch (Phase 14)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

from fastapi import HTTPException, status
from pydantic import BaseModel, Field

from app.workforce.roster import WORKFORCE_ROSTER

ChainStatus = Literal["queued", "running", "completed", "failed"]


class ChainStepRequest(BaseModel):
    member_id: str
    prompt: str = Field(min_length=1, max_length=4000)
    skill: str | None = None


@dataclass
class ChainRecord:
    id: str
    steps: list[dict[str, str]]
    status: ChainStatus
    task_ids: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    error: str | None = None


class OrchestrationForge:
    """Tracks multi-step chains and advances them as child tasks complete."""

    def __init__(self) -> None:
        self._chains: dict[str, ChainRecord] = {}
        self._order: list[str] = []

    @staticmethod
    def _validate_steps(steps: list[ChainStepRequest]) -> list[dict[str, str]]:
        if not steps:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="chain requires steps")
        if len(steps) > 8:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="max 8 chain steps")

        roster_ids = {member["id"] for member in WORKFORCE_ROSTER}
        normalized: list[dict[str, str]] = []
        for step in steps:
            if step.member_id not in roster_ids:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Unknown workforce member {step.member_id!r}",
                )
            item: dict[str, str] = {
                "member_id": step.member_id,
                "prompt": step.prompt.strip(),
            }
            if step.skill:
                item["skill"] = step.skill
            normalized.append(item)
        return normalized

    def create_chain(self, steps: list[ChainStepRequest]) -> ChainRecord:
        normalized = self._validate_steps(steps)
        chain_id = uuid.uuid4().hex[:12]
        record = ChainRecord(id=chain_id, steps=normalized, status="queued")
        self._chains[chain_id] = record
        self._order.insert(0, chain_id)
        return record

    def get_chain(self, chain_id: str) -> ChainRecord | None:
        return self._chains.get(chain_id)

    def list_chains(self, *, limit: int = 20) -> list[ChainRecord]:
        capped = max(1, min(limit, 50))
        return [self._chains[cid] for cid in self._order[:capped] if cid in self._chains]

    def register_task(self, chain_id: str, task_id: str) -> None:
        chain = self._chains.get(chain_id)
        if chain is None:
            return
        chain.task_ids.append(task_id)
        if chain.status == "queued":
            chain.status = "running"

    def mark_chain_completed(self, chain_id: str) -> None:
        chain = self._chains.get(chain_id)
        if chain is None:
            return
        chain.status = "completed"
        chain.completed_at = datetime.now(UTC)

    def mark_chain_failed(self, chain_id: str, error: str) -> None:
        chain = self._chains.get(chain_id)
        if chain is None:
            return
        chain.status = "failed"
        chain.error = error
        chain.completed_at = datetime.now(UTC)

    def status(self) -> dict[str, int]:
        chains = list(self._chains.values())
        return {
            "chains_total": len(chains),
            "chains_queued": sum(1 for chain in chains if chain.status == "queued"),
            "chains_running": sum(1 for chain in chains if chain.status == "running"),
            "chains_completed": sum(1 for chain in chains if chain.status == "completed"),
            "chains_failed": sum(1 for chain in chains if chain.status == "failed"),
        }