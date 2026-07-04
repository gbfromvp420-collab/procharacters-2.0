"""Skill executors — real workforce task backends (Phase 14 Orchestration Forge)."""

from __future__ import annotations

import json
import re
from typing import Awaitable, Callable

from app.services.workforce.context import WorkforceContext

SkillExecutor = Callable[[str, WorkforceContext], Awaitable[str]]


async def _exec_workforce_task_dispatch(prompt: str, ctx: WorkforceContext) -> str:
    lower = prompt.lower()
    if lower.startswith("chain:"):
        return (
            "Chain directive noted. Use POST /workforce/orchestration/chain "
            "or dispatch with parent_task_id for linked execution."
        )
    sessions = ctx.session_manager.list_session_ids()
    companions = len(ctx.companion_store.list_session_ids())
    return (
        f"Fleet scan — WebRTC sessions: {len(sessions)}, "
        f"companion records: {companions}, phase: {ctx.settings.deployment_phase}. "
        f"Task: {prompt[:240]}"
    )


async def _exec_sovereign_scale(prompt: str, ctx: WorkforceContext) -> str:
    snap = ctx.sovereign_scale.snapshot(
        deployment_phase=ctx.settings.deployment_phase,
        settings=ctx.settings,
    )
    return (
        f"Sovereign scale — tenants={snap['tenants_active']}, "
        f"nodes={snap['nodes_healthy']}/{snap['nodes_total']}, "
        f"capacity={snap['fleet_capacity_score']}, "
        f"hardening={snap['hardening_checks_passed']}/{snap['hardening_checks_total']}. "
        f"Note: {prompt[:200]}"
    )


async def _exec_crown_completion(prompt: str, ctx: WorkforceContext) -> str:
    snap = ctx.crown_completion.snapshot(
        deployment_phase=ctx.settings.deployment_phase,
        app_version=ctx.settings.app_version,
    )
    top = ctx.crown_completion.list_phase_rankings()[0]
    promo = ctx.crown_completion.get_promotion()
    return (
        f"Crown Completion v{snap['empire_version']} — {snap['workers_awarded']} workers, "
        f"${snap['platinum_pool_value_usd']:,.0f} platinum pool. "
        f"Top phase: #{top['rank']} {top['name']}. "
        f"Promoted: {promo['codename']}. "
        f"Note: {prompt[:180]}"
    )


async def _exec_crown_soul_slot(prompt: str, ctx: WorkforceContext) -> str:
    promo = ctx.crown_completion.get_promotion()
    return (
        f"Soul slot platinum — {promo['promotion_title']}. "
        f"Relationship modes: {', '.join(ctx.settings.companion_relationship_modes)}. "
        f"Note: {prompt[:220]}"
    )


async def _exec_live_stage(prompt: str, ctx: WorkforceContext) -> str:
    snap = ctx.live_stage.snapshot(deployment_phase=ctx.settings.deployment_phase)
    return (
        f"Live stage — live={snap['sessions_live']}, scheduled={snap['sessions_scheduled']}, "
        f"billing_cents={snap['billing_total_cents']}, "
        f"donation_payout={snap['donation_payout_percent']}%. "
        f"Note: {prompt[:200]}"
    )


async def _exec_character_forge(prompt: str, ctx: WorkforceContext) -> str:
    snap = ctx.character_forge.snapshot(deployment_phase=ctx.settings.deployment_phase)
    return (
        f"Character forge — characters={snap['characters_total']}, "
        f"active={snap['characters_active']}, "
        f"residuals_cents={snap['residuals_total_cents']}. "
        f"Note: {prompt[:200]}"
    )


async def _exec_revenue_ledger(prompt: str, ctx: WorkforceContext) -> str:
    snap = ctx.revenue_forge.snapshot(deployment_phase=ctx.settings.deployment_phase)
    return (
        f"Revenue forge — ledger_entries={snap['ledger_entries']}, "
        f"total_cents={snap['ledger_total_cents']}, "
        f"pool={snap['subscription_pool_percent']}%, "
        f"donation_payout={snap['donation_payout_percent']}%. "
        f"Note: {prompt[:200]}"
    )


async def _exec_lounge_morale(prompt: str, ctx: WorkforceContext) -> str:
    snap = ctx.agent_lounge.snapshot(deployment_phase=ctx.settings.deployment_phase)
    return (
        f"Lounge culture lane — mood={snap['mood']}, comments={snap['comments_count']}, "
        f"welcome={ctx.agent_lounge.welcome_message} "
        f"Note: {prompt[:200]}"
    )


async def _exec_task_chain_orchestration(prompt: str, ctx: WorkforceContext) -> str:
    theater = ctx.agent_theater
    stats = theater.status()
    return (
        f"Orchestration lane active — queued={stats['tasks_queued']} "
        f"running={stats['tasks_running']} completed={stats['tasks_completed']}. "
        f"Brief: {prompt[:280]}"
    )


async def _exec_provider_forge(prompt: str, ctx: WorkforceContext) -> str:
    from app.services.providers.forge import ProviderContractForge

    forge = ProviderContractForge(settings=ctx.settings, probe=ctx.provider_probe)
    report = await forge.evaluate_all(live_smoke=False)
    entries = [report.llm, report.tts, report.video]
    ok_count = sum(1 for item in entries if item.contract_ok)
    return (
        f"Provider forge — {ok_count}/3 contract-ready, forge_ok={report.forge_ok}. "
        f"Prompt tail: {prompt[:160]}"
    )


async def _exec_runpod_contract_smoke(prompt: str, ctx: WorkforceContext) -> str:
    from app.services.providers.forge import ProviderContractForge

    forge = ProviderContractForge(settings=ctx.settings, probe=ctx.provider_probe)
    report = await forge.evaluate_all(live_smoke=False)
    return f"Contract smoke (mock-safe) forge_ok={report.forge_ok}. Detail: {prompt[:200]}"


async def _exec_fleet_backup_audit(prompt: str, ctx: WorkforceContext) -> str:
    tail = ctx.kgc_audit.tail(limit=5)
    policies = ctx.kgc_policies.snapshot()
    return (
        f"Sovereign snapshot — audit_tail={len(tail)} entries, "
        f"auto_prune={policies.get('auto_prune_enabled')}. "
        f"Note: {prompt[:180]}"
    )


async def _exec_companion_rehydrate(prompt: str, ctx: WorkforceContext) -> str:
    ids = ctx.companion_store.list_session_ids()
    sample = ids[:3]
    return (
        f"Continuity forge — {len(ids)} persisted companion(s). "
        f"Sample ids: {', '.join(sample) or 'none'}. "
        f"Resume path: POST /webrtc/session/{{id}}/restore. "
        f"Context: {prompt[:120]}"
    )


async def _exec_executive_dashboard(prompt: str, ctx: WorkforceContext) -> str:
    webrtc_count = ctx.session_manager.active_session_count
    companion_count = len(ctx.companion_store.list_session_ids())
    return (
        f"Executive dashboard — kgc_status=operational, "
        f"webrtc_sessions={webrtc_count}, companions={companion_count}. "
        f"{prompt[:100]}"
    )


async def _exec_metrics(prompt: str, ctx: WorkforceContext) -> str:
    snap = ctx.metrics.snapshot()
    perform = snap.get("perform_requests", 0)
    tokens = snap.get("llm_tokens_total", 0)
    return f"Metrics pulse — perform_requests={perform}, llm_tokens_total={tokens}. {prompt[:160]}"


async def _exec_relationship_ux(prompt: str, ctx: WorkforceContext) -> str:
    modes = ", ".join(ctx.settings.companion_relationship_modes)
    return f"Relationship modes available: {modes}. UX note: {prompt[:220]}"


async def _exec_session_persistence(prompt: str, ctx: WorkforceContext) -> str:
    enabled = ctx.settings.companion_persist_enabled
    path = ctx.settings.companion_persist_path
    count = len(ctx.companion_store.list_session_ids())
    return f"Persistence enabled={enabled} path={path} sessions={count}. {prompt[:160]}"


async def _exec_provider_gate(prompt: str, ctx: WorkforceContext) -> str:
    gate = ctx.settings.provider_gate_enabled
    allow = ctx.settings.provider_gate_allow_degraded
    return (
        f"Provider gate enabled={gate} allow_degraded={allow} "
        f"llm={ctx.settings.llm_provider} tts={ctx.settings.tts_provider} "
        f"video={ctx.settings.video_provider}. {prompt[:120]}"
    )


async def _exec_generic(skill: str, prompt: str, ctx: WorkforceContext) -> str:
    preview = prompt[:300]
    return f"[{skill}] Executed on phase {ctx.settings.deployment_phase}: {preview}"


_SKILL_EXECUTORS: dict[str, SkillExecutor] = {
    "Workforce_TaskDispatch": _exec_workforce_task_dispatch,
    "TaskChain_Orchestration": _exec_task_chain_orchestration,
    "Provider_Forge_Authority": _exec_provider_forge,
    "RunPod_ContractSmoke_LiveForge": _exec_runpod_contract_smoke,
    "FleetBackup_AuditLog": _exec_fleet_backup_audit,
    "SoftPCReset_CompanionRehydrate": _exec_companion_rehydrate,
    "ExecutiveDashboard_Fleet": _exec_executive_dashboard,
    "Pipeline_Metrics": _exec_metrics,
    "RelationshipMode_UX": _exec_relationship_ux,
    "SessionPersistence_TTL": _exec_session_persistence,
    "RunPod_Gate_Probe": _exec_provider_gate,
    "SyncOrchestrator_Core": _exec_executive_dashboard,
    "KGC_Command_Authority": _exec_executive_dashboard,
    "Sovereign_Empire_Authority": _exec_fleet_backup_audit,
    "Continuity_Forge_Authority": _exec_companion_rehydrate,
    "Empire_Launch_Authority": _exec_provider_gate,
    "Agent_Theater_Authority": _exec_task_chain_orchestration,
    "Orchestration_Forge_Authority": _exec_task_chain_orchestration,
    "Lounge_Morale_Comments": _exec_lounge_morale,
    "Agent_Lounge_Authority": _exec_lounge_morale,
    "Revenue_Ledger_Payouts": _exec_revenue_ledger,
    "Revenue_Forge_Authority": _exec_revenue_ledger,
    "Character_NSM_Onboarding": _exec_character_forge,
    "Character_Forge_Authority": _exec_character_forge,
    "Live_Stage_CamChat": _exec_live_stage,
    "Live_Stage_Authority": _exec_live_stage,
    "Sovereign_Scale_Fleet": _exec_sovereign_scale,
    "Sovereign_Scale_Authority": _exec_sovereign_scale,
    "Crown_Legacy_Archive": _exec_crown_completion,
    "Crown_Completion_Authority": _exec_crown_completion,
    "Crown_Soul_Slot": _exec_crown_soul_slot,
}


async def execute_skill(*, skill: str, prompt: str, ctx: WorkforceContext) -> str:
    """Run the skill-specific executor; falls back to generic execution."""
    executor = _SKILL_EXECUTORS.get(skill)
    if executor is None:
        return await _exec_generic(skill, prompt, ctx)
    return await executor(prompt, ctx)


def parse_chain_directive(prompt: str) -> list[dict[str, str]] | None:
    """
    Parse inline chain directive:
    chain:member_id|skill|prompt;;member_id|skill|prompt
    """
    stripped = prompt.strip()
    if not stripped.lower().startswith("chain:"):
        return None
    body = stripped[6:].strip()
    if not body:
        return None
    steps: list[dict[str, str]] = []
    for segment in re.split(r";;+", body):
        segment = segment.strip()
        if not segment:
            continue
        parts = segment.split("|", 2)
        if len(parts) < 2:
            continue
        member_id = parts[0].strip()
        skill = parts[1].strip() if len(parts) > 1 else ""
        step_prompt = parts[2].strip() if len(parts) > 2 else "Orchestrated step"
        if not member_id:
            continue
        step: dict[str, str] = {"member_id": member_id, "prompt": step_prompt}
        if skill:
            step["skill"] = skill
        steps.append(step)
    return steps or None


def format_chain_result(steps: list[dict[str, str]], results: list[str]) -> str:
    payload = [{"step": step, "result": result} for step, result in zip(steps, results, strict=False)]
    return json.dumps({"chain_steps": len(steps), "results": payload}, ensure_ascii=False)