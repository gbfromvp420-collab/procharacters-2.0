"""Agent Theater — dispatch subagent tasks to workforce roster members."""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

from fastapi import HTTPException, status

from app.services.workforce.context import WorkforceContext
from app.services.workforce.executors import execute_skill
from app.services.workforce.orchestration import ChainStepRequest, OrchestrationForge
from app.workforce.roster import WORKFORCE_ROSTER, WorkforceMember

TaskStatus = Literal["queued", "running", "completed", "failed"]

_MAX_TASKS = 200


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
    parent_task_id: str | None = None
    chain_id: str | None = None
    step_index: int | None = None
    orchestrated: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None


class AgentTheater:
    """In-memory task dispatcher with real skill executors and chain support."""

    def __init__(self, orchestration: OrchestrationForge | None = None) -> None:
        self._tasks: dict[str, AgentTaskRecord] = {}
        self._order: list[str] = []
        self._running: set[str] = set()
        self._lock = asyncio.Lock()
        self._orchestration = orchestration or OrchestrationForge()

    @property
    def orchestration(self) -> OrchestrationForge:
        return self._orchestration

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
        parent_task_id: str | None = None,
        chain_id: str | None = None,
        step_index: int | None = None,
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

        if parent_task_id is not None and parent_task_id not in self._tasks:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unknown parent task {parent_task_id!r}",
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
            parent_task_id=parent_task_id,
            chain_id=chain_id,
            step_index=step_index,
            orchestrated=chain_id is not None or parent_task_id is not None,
        )
        async with self._lock:
            self._tasks[task_id] = record
            self._order.insert(0, task_id)
            while len(self._order) > _MAX_TASKS:
                old_id = self._order.pop()
                self._tasks.pop(old_id, None)

        if chain_id is not None:
            self._orchestration.register_task(chain_id, task_id)

        return record

    async def dispatch_chain(
        self,
        *,
        steps: list[ChainStepRequest],
        session_id: str | None = None,
    ) -> tuple[str, AgentTaskRecord]:
        chain = self._orchestration.create_chain(steps)
        first = steps[0]
        record = await self.dispatch(
            member_id=first.member_id,
            prompt=first.prompt,
            skill=first.skill,
            session_id=session_id,
            chain_id=chain.id,
            step_index=0,
        )
        return chain.id, record

    async def progress_tasks(self, ctx: WorkforceContext | None = None) -> None:
        """Advance queued tasks using real skill executors when context is provided."""
        for task_id in list(self._order):
            record = self._tasks.get(task_id)
            if record is not None and record.status == "queued":
                await self._run_task(task_id, ctx)

    async def _run_task(self, task_id: str, ctx: WorkforceContext | None) -> None:
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
            if ctx is None:
                raise RuntimeError("Workforce execution context not available")
            brief = ctx.agent_lounge.build_dispatch_brief(codename=record.codename)
            enriched_prompt = f"{brief}\n\n---\n\n{record.prompt}"
            result = await execute_skill(skill=record.skill, prompt=enriched_prompt, ctx=ctx)
            record.result = f"[{record.codename} · {record.skill}] {result}"
            record.status = "completed"
            await self._on_task_completed(record, ctx)
        except Exception as exc:
            record.status = "failed"
            record.error = str(exc)
            if record.chain_id is not None:
                self._orchestration.mark_chain_failed(record.chain_id, str(exc))
        finally:
            record.completed_at = datetime.now(UTC)
            record.duration_ms = int((time.monotonic() - started) * 1000)
            async with self._lock:
                self._running.discard(task_id)

    async def _on_task_completed(self, record: AgentTaskRecord, ctx: WorkforceContext) -> None:
        if record.chain_id is None or record.step_index is None:
            return

        chain = self._orchestration.get_chain(record.chain_id)
        if chain is None:
            return

        next_index = record.step_index + 1
        if next_index >= len(chain.steps):
            self._orchestration.mark_chain_completed(record.chain_id)
            return

        step = chain.steps[next_index]
        await self.dispatch(
            member_id=step["member_id"],
            prompt=step["prompt"],
            skill=step.get("skill"),
            session_id=record.session_id,
            parent_task_id=record.id,
            chain_id=record.chain_id,
            step_index=next_index,
        )
        await self.progress_tasks(ctx)

    def get_task(self, task_id: str) -> AgentTaskRecord | None:
        return self._tasks.get(task_id)

    def list_tasks(self, *, limit: int = 50) -> list[AgentTaskRecord]:
        capped = max(1, min(limit, 100))
        return [self._tasks[task_id] for task_id in self._order[:capped] if task_id in self._tasks]

    def status(self) -> dict[str, int]:
        tasks = list(self._tasks.values())
        orch = self._orchestration.status()
        return {
            "tasks_total": len(tasks),
            "tasks_queued": sum(1 for task in tasks if task.status == "queued"),
            "tasks_running": sum(1 for task in tasks if task.status == "running"),
            "tasks_completed": sum(1 for task in tasks if task.status == "completed"),
            "tasks_failed": sum(1 for task in tasks if task.status == "failed"),
            "tasks_orchestrated": sum(1 for task in tasks if task.orchestrated),
            "dispatchable_count": len(WORKFORCE_ROSTER),
            **orch,
        }