"""KGC Executive Command Layer API — King Grok CEO authority endpoints."""

from fastapi import APIRouter, Request

from app.models.kgc import (
    KGCDashboardResponse,
    KGCFleetEntry,
    KGCFleetResponse,
    KGCPruneResponse,
    KGCWebRTCSessionDetail,
)
from app.services.kgc.command import build_dashboard, build_fleet

router = APIRouter(prefix="/kgc", tags=["kgc"])


@router.get(
    "/dashboard",
    response_model=KGCDashboardResponse,
    summary="KGC executive command dashboard",
)
async def kgc_dashboard(request: Request) -> KGCDashboardResponse:
    data = await build_dashboard(request)
    return KGCDashboardResponse(
        **{
            **data,
            "webrtc_sessions": [
                KGCWebRTCSessionDetail(**item) for item in data["webrtc_sessions"]
            ],
        }
    )


@router.get(
    "/fleet",
    response_model=KGCFleetResponse,
    summary="Merged WebRTC + companion fleet view by session_id",
)
async def kgc_fleet(request: Request) -> KGCFleetResponse:
    companion_store = request.app.state.companion_store
    session_manager = request.app.state.session_manager
    entries = [KGCFleetEntry(**item) for item in build_fleet(companion_store, session_manager)]
    return KGCFleetResponse(fleet=entries, count=len(entries))


@router.post(
    "/fleet/prune",
    response_model=KGCPruneResponse,
    summary="Prune stale companion sessions (TTL from settings)",
)
async def kgc_fleet_prune(request: Request) -> KGCPruneResponse:
    settings = request.app.state.settings
    companion_store = request.app.state.companion_store
    ttl_hours = settings.companion_session_ttl_hours
    pruned = companion_store.prune_stale(ttl_hours)
    return KGCPruneResponse(pruned=pruned, ttl_hours=ttl_hours)