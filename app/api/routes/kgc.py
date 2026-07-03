"""KGC Executive Command Layer API — King Grok CEO authority endpoints."""

import json

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import Response

from app.models.kgc import (
    KGCAuditEntry,
    KGCAuditResponse,
    KGCCloneRequest,
    KGCCloneResponse,
    KGCDashboardResponse,
    KGCFleetBackupResponse,
    KGCFleetEntry,
    KGCFleetResponse,
    KGCFleetRestoreRequest,
    KGCFleetRestoreResponse,
    KGCImportRequest,
    KGCImportResponse,
    KGCPoliciesResponse,
    KGCPoliciesUpdate,
    KGCPruneResponse,
    KGCWebRTCSessionDetail,
)
from app.services.kgc.audit import log_action
from app.services.kgc.backup import build_fleet_backup, restore_fleet_backup
from app.services.kgc.command import build_dashboard, build_fleet

router = APIRouter(prefix="/kgc", tags=["kgc"])


def _fleet_backup_payload(request: Request) -> dict:
    return build_fleet_backup(
        request.app.state.companion_store,
        request.app.state.kgc_policies,
        request.app.state.kgc_audit,
    )


def _fleet_backup_response(request: Request, *, as_download: bool) -> Response:
    payload = _fleet_backup_payload(request)
    body = json.dumps(payload, indent=2) + "\n"
    if as_download:
        return Response(
            content=body,
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="kgc-fleet-backup.json"'},
        )
    return Response(content=body, media_type="application/json")


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
    log_action("fleet.prune", f"pruned={pruned} ttl_hours={ttl_hours}")
    return KGCPruneResponse(pruned=pruned, ttl_hours=ttl_hours)


@router.post(
    "/fleet/clone",
    response_model=KGCCloneResponse,
    summary="Clone a companion session to a new session_id",
)
async def kgc_fleet_clone(request: Request, payload: KGCCloneRequest) -> KGCCloneResponse:
    companion_store = request.app.state.companion_store
    try:
        target_id = companion_store.clone_session(
            payload.source_session_id,
            payload.target_session_id,
        )
    except ValueError as exc:
        log_action(
            "fleet.clone",
            f"source={payload.source_session_id} target={payload.target_session_id}",
            result="error",
        )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    log_action(
        "fleet.clone",
        f"source={payload.source_session_id} target={target_id}",
    )
    return KGCCloneResponse(
        source_session_id=payload.source_session_id,
        target_session_id=target_id,
    )


@router.post(
    "/fleet/import",
    response_model=KGCImportResponse,
    summary="Import a single companion session payload",
)
async def kgc_fleet_import(request: Request, payload: KGCImportRequest) -> KGCImportResponse:
    companion_store = request.app.state.companion_store
    imported = companion_store.import_session(payload.session_id, payload.data)
    log_action(
        "fleet.import",
        f"session_id={payload.session_id} imported={imported}",
        result="ok" if imported else "error",
    )
    if not imported:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid companion session import payload",
        )
    return KGCImportResponse(session_id=payload.session_id, imported=True)


@router.get(
    "/fleet/backup",
    summary="Download full fleet backup (companion sessions, policies, audit tail)",
)
async def kgc_fleet_backup_get(request: Request) -> Response:
    log_action("fleet.backup", "method=GET")
    return _fleet_backup_response(request, as_download=True)


@router.post(
    "/fleet/backup",
    summary="Download full fleet backup (companion sessions, policies, audit tail)",
)
async def kgc_fleet_backup_post(request: Request) -> Response:
    log_action("fleet.backup", "method=POST")
    return _fleet_backup_response(request, as_download=True)


@router.post(
    "/fleet/restore",
    response_model=KGCFleetRestoreResponse,
    summary="Restore fleet from backup JSON (merge by session_id)",
)
async def kgc_fleet_restore(
    request: Request,
    payload: KGCFleetRestoreRequest,
) -> KGCFleetRestoreResponse:
    companion_store = request.app.state.companion_store
    policies = request.app.state.kgc_policies
    result = restore_fleet_backup(
        companion_store,
        policies,
        payload.model_dump(exclude_none=True),
    )
    log_action(
        "fleet.restore",
        f"sessions_merged={result['sessions_merged']} sessions_total={result['sessions_total']}",
    )
    return KGCFleetRestoreResponse(**result)


@router.get(
    "/policies",
    response_model=KGCPoliciesResponse,
    summary="Get global KGC companion policies",
)
async def kgc_get_policies(request: Request) -> KGCPoliciesResponse:
    snapshot = request.app.state.kgc_policies.snapshot()
    return KGCPoliciesResponse(**snapshot)


@router.patch(
    "/policies",
    response_model=KGCPoliciesResponse,
    summary="Update global KGC companion policies",
)
async def kgc_update_policies(
    request: Request,
    payload: KGCPoliciesUpdate,
) -> KGCPoliciesResponse:
    policies = request.app.state.kgc_policies
    updated = policies.update(
        default_relationship_mode=payload.default_relationship_mode,
        default_system_prompt=payload.default_system_prompt,
        auto_prune_enabled=payload.auto_prune_enabled,
    )
    log_action("policies.update", json.dumps(updated, sort_keys=True))
    return KGCPoliciesResponse(**updated)


@router.get(
    "/audit",
    response_model=KGCAuditResponse,
    summary="Recent KGC audit log entries (ring buffer tail)",
)
async def kgc_audit(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
) -> KGCAuditResponse:
    entries = [
        KGCAuditEntry(**item)
        for item in request.app.state.kgc_audit.tail(limit=limit)
    ]
    return KGCAuditResponse(entries=entries, count=len(entries))