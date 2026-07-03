from fastapi import APIRouter, HTTPException, Request, status

from app.models.companion import (
    CompanionCatalogResponse,
    CompanionConfig,
    CompanionConfigUpdate,
    CompanionSessionSummary,
    ConversationHistoryResponse,
)
from app.services.companion.catalog import (
    get_avatar_catalog,
    get_prompt_presets,
    get_voice_catalog,
)
from app.services.companion.store import SessionCompanionStore

router = APIRouter(prefix="/companion", tags=["companion"])


def _store(request: Request) -> SessionCompanionStore:
    return request.app.state.companion_store


@router.get(
    "/catalog",
    response_model=CompanionCatalogResponse,
    summary="List available avatars, voices, and prompt presets",
)
async def get_companion_catalog(request: Request) -> CompanionCatalogResponse:
    settings = request.app.state.settings
    return CompanionCatalogResponse(
        avatars=get_avatar_catalog(settings),
        voices=get_voice_catalog(settings),
        prompt_presets=get_prompt_presets(),
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

    cfg = store.set_config(
        session_id,
        avatar_id=payload.avatar_id,
        voice=payload.voice,
        system_prompt=payload.system_prompt,
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