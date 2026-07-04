"""Build WorkforceContext from FastAPI app state."""

from __future__ import annotations

from fastapi import Request

from app.services.workforce.context import WorkforceContext


def build_workforce_context(request: Request) -> WorkforceContext:
    return WorkforceContext(
        settings=request.app.state.settings,
        companion_store=request.app.state.companion_store,
        session_manager=request.app.state.session_manager,
        metrics=request.app.state.metrics,
        provider_probe=request.app.state.provider_probe,
        kgc_policies=request.app.state.kgc_policies,
        kgc_audit=request.app.state.kgc_audit,
        agent_theater=request.app.state.agent_theater,
        agent_lounge=request.app.state.agent_lounge,
    )