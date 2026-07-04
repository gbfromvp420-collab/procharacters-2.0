"""Agent Theater — dispatch subagent tasks to workforce roster members."""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

from fastapi import HTTPException, status

from app.workforce.roster import WORKFORCE_ROSTER, WorkforceMember

TaskStatus = Literal["queued", "running", "completed", "failed"]

_MAX_TASKS = 200
_MOCK_DELAY_BASE_MS = 120
_MOCK_DELAY_JITTER_MS = 180


@dataclass
class AgentTaskRecord:
    id: str
    member_id: str
    codename: str
    skill: str
    prompt: str
    status: TaskStatus
    result: str | None = None
    error: str | None = None
    session_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None


class AgentTheater:
    """In-memory task dispatcher that routes prompts to roster subagents."""

    def __init__(self) -> None:
        self._tasks: dict[str, AgentTaskRecord] = {}
        self._order: list[str] = []
        self._running: set[str] = set()
        self._lock = asyncio.Lock()

    @staticmethod
    def _find_member(member_id: str) -> WorkforceMember | None:
        for member in WORKFORCE_ROSTER:
            if member["id"] == member_id:
                return member
        return None

    @staticmethod
    def _resolve_skill(member: WorkforceMember, skill: str | None) -> str:
        skills = member["skills"]
        if skill:
            if skill not in skills:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Member {member['codename']} does not have skill {skill!r}",
                )
            return skill
        return skills[0]

    async def dispatch(
        self,
        *,
        member_id: str,
        prompt: str,
        skill: str | None = None,
        session_id: str | None = None,
    ) -> AgentTaskRecord:
        prompt = prompt.strip()
        if not prompt:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="prompt must not be empty")

        member = self._find_member(member_id)
        if member is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unknown workforce member {member_id!r}",
            )

        resolved_skill = self._resolve_skill(member, skill)
        task_id = uuid.uuid4().hex[:12]
        record = AgentTaskRecord(
            id=task_id,
            member_id=member_id,
            codename=member["codename"],
            skill=resolved_skill,
            prompt=prompt,
            status="queued",
            session_id=session_id,
        )
        async with self._lock:
            self._tasks[task_id] = record
            self._order.insert(0, task_id)
            while len(self._order) > _MAX_TASKS:
                old_id = self._order.pop()
                self._tasks.pop(old_id, None)

        return record

    async def progress_tasks(self) -> None:
        """Advance queued mock tasks (also invoked on theater read endpoints)."""
        for task_id in list(self._order):
            record = self._tasks.get(task_id)
            if record is not None and record.status == "queued":
                await self._run_task(task_id)

    async def _run_task(self, task_id: str) -> None:
        record = self._tasks.get(task_id)
        if record is None:
            return

        async with self._lock:
            if task_id in self._running:
                return
            self._running.add(task_id)

        record.status = "running"
        record.started_at = datetime.now(UTC)
        started = time.monotonic()

        try:
            delay_ms = _MOCK_DELAY_BASE_MS + (hash(record.prompt) % _MOCK_DELAY_JITTER_MS)
            await asyncio.sleep(delay_ms / 1000.0)
            preview = record.prompt[:200]
            record.result = f"[{record.codename} · {record.skill}] Completed: {preview}"
            record.status = "completed"
        except Exception as exc:
            record.status = "failed"
            record.error = str(exc)
        finally:
            record.completed_at = datetime.now(UTC)
            record.duration_ms = int((time.monotonic() - started) * 1000)
            async with self._lock:
                self._running.discard(task_id)

    def get_task(self, task_id: str) -> AgentTaskRecord | None:
        return self._tasks.get(task_id)

    def list_tasks(self, *, limit: int = 50) -> list[AgentTaskRecord]:
        capped = max(1, min(limit, 100))
        return [self._tasks[task_id] for task_id in self._order[:capped] if task_id in self._tasks]

    def status(self) -> dict[str, int]:
        tasks = list(self._tasks.values())
        return {
            "tasks_total": len(tasks),
            "tasks_queued": sum(1 for task in tasks if task.status == "queued"),
            "tasks_running": sum(1 for task in tasks if task.status == "running"),
            "tasks_completed": sum(1 for task in tasks if task.status == "completed"),
            "tasks_failed": sum(1 for task in tasks if task.status == "failed"),
            "dispatchable_count": len(WORKFORCE_ROSTER),
        }