import json

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse, Response

from app.models.companion import (
    CompanionCatalogResponse,
    CompanionConfig,
    CompanionConfigUpdate,
    CompanionHeartbeatResponse,
    CompanionSessionSummary,
    ConversationHistoryResponse,
)
from app.services.companion.catalog import (
    get_avatar_catalog,
    get_prompt_presets,
    get_relationship_modes,
    get_voice_catalog,
)
from app.services.companion.store import SessionCompanionStore

router = APIRouter(prefix="/companion", tags=["companion"])


def _store(request: Request) -> SessionCompanionStore:
    return request.app.state.companion_store


@router.get(
    "/catalog",
    response_model=CompanionCatalogResponse,
    summary="List available avatars, voices, prompt presets, and relationship modes",
)
async def get_companion_catalog(request: Request) -> CompanionCatalogResponse:
    settings = request.app.state.settings
    return CompanionCatalogResponse(
        avatars=get_avatar_catalog(settings),
        voices=get_voice_catalog(settings),
        prompt_presets=get_prompt_presets(),
        relationship_modes=get_relationship_modes(settings),
    )


@router.get(
    "/sessions",
    response_model=list[CompanionSessionSummary],
    summary="List persisted companion sessions (resume-after-restart UX)",
)
async def list_companion_sessions(request: Request) -> list[CompanionSessionSummary]:
    store = _store(request)
    return [CompanionSessionSummary(**item) for item in store.list_persisted_sessions()]


@router.get(
    "/{session_id}/config",
    response_model=CompanionConfig,
    summary="Get companion avatar/voice/prompt config for a session",
)
async def get_companion_config(request: Request, session_id: str) -> CompanionConfig:
    store = _store(request)
    cfg = store.get_config(session_id)
    return CompanionConfig(**cfg)


@router.patch(
    "/{session_id}/config",
    response_model=CompanionConfig,
    summary="Update companion config for a session",
)
async def update_companion_config(
    request: Request,
    session_id: str,
    payload: CompanionConfigUpdate,
) -> CompanionConfig:
    settings = request.app.state.settings
    store = _store(request)

    if payload.avatar_id is not None and payload.avatar_id not in settings.companion_avatars:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown avatar_id. Allowed: {settings.companion_avatars}",
        )
    if payload.voice is not None and payload.voice not in settings.companion_voices:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown voice. Allowed: {settings.companion_voices}",
        )
    if (
        payload.relationship_mode is not None
        and payload.relationship_mode
        and payload.relationship_mode not in settings.companion_relationship_modes
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown relationship_mode. Allowed: {settings.companion_relationship_modes}",
        )

    cfg = store.set_config(
        session_id,
        avatar_id=payload.avatar_id,
        voice=payload.voice,
        system_prompt=payload.system_prompt,
        relationship_mode=payload.relationship_mode,
    )
    return CompanionConfig(**cfg)


@router.get(
    "/{session_id}/history",
    response_model=ConversationHistoryResponse,
    summary="Get stored conversation history for a session",
)
async def get_conversation_history(
    request: Request,
    session_id: str,
) -> ConversationHistoryResponse:
    store = _store(request)
    messages = store.get_messages(session_id)
    return ConversationHistoryResponse(
        messages=messages,
        turn_count=len(messages) // 2,
    )


@router.get(
    "/{session_id}/export",
    summary="Download conversation history as JSON or plain text",
)
async def export_conversation(
    request: Request,
    session_id: str,
    format: str = Query(default="json", pattern="^(json|txt)$"),
) -> Response:
    store = _store(request)
    cfg = store.get_config(session_id)
    messages = store.get_messages(session_id)

    if format == "txt":
        lines: list[str] = [
            f"Session: {session_id}",
            f"Avatar: {cfg['avatar_id']}",
            f"Voice: {cfg['voice']}",
            f"Relationship mode: {cfg['relationship_mode'] or '(none)'}",
            f"Turns: {len(messages) // 2}",
            "",
        ]
        for message in messages:
            role = message.role.upper()
            lines.append(f"[{role}] {message.content}")
            lines.append("")
        body = "\n".join(lines).rstrip() + "\n"
        return PlainTextResponse(
            content=body,
            headers={
                "Content-Disposition": f'attachment; filename="companion-{session_id}.txt"'
            },
        )

    payload = {
        "session_id": session_id,
        "config": cfg,
        "messages": [message.model_dump() for message in messages],
        "turn_count": len(messages) // 2,
    }
    return Response(
        content=json.dumps(payload, indent=2) + "\n",
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="companion-{session_id}.json"'
        },
    )


@router.post(
    "/{session_id}/heartbeat",
    response_model=CompanionHeartbeatResponse,
    summary="Touch session activity and return current status",
)
async def companion_heartbeat(
    request: Request,
    session_id: str,
) -> CompanionHeartbeatResponse:
    store = _store(request)
    store.touch(session_id)
    cfg = store.get_config(session_id)
    return CompanionHeartbeatResponse(
        session_id=session_id,
        status="active",
        turn_count=cfg["turn_count"],
        last_active_at=cfg["last_active_at"],
        avatar_id=cfg["avatar_id"],
        relationship_mode=cfg["relationship_mode"],
    )


@router.delete(
    "/{session_id}/history",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Clear stored conversation history (keeps config)",
)
async def clear_conversation_history(request: Request, session_id: str) -> None:
    store = _store(request)
    store.clear_history(session_id)


@router.delete(
    "/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Fully remove companion session (config + history)",
)
async def delete_companion_session(request: Request, session_id: str) -> None:
    store = _store(request)
    if not store.remove(session_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown companion session: {session_id}",
        )