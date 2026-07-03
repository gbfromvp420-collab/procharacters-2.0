import logging

from fastapi import APIRouter, HTTPException, Request, status

from app.services.observability.metrics import MetricsCollector

from app.models.webrtc import (
    ActiveSessionsResponse,
    IceCandidateRequest,
    IceCandidatesResponse,
    SessionCreatedResponse,
    WebRTCAnswerResponse,
    WebRTCOfferRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webrtc", tags=["webrtc"])


@router.post(
    "/session",
    response_model=SessionCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a signaling session",
)
async def create_session(request: Request) -> SessionCreatedResponse:
    session_manager = request.app.state.session_manager
    metrics: MetricsCollector = request.app.state.metrics
    session = session_manager.create_session()
    metrics.increment_sessions_created()
    return SessionCreatedResponse(
        session_id=session.session_id,
        ice_servers=session_manager.ice_servers,
    )


@router.post(
    "/offer",
    response_model=WebRTCAnswerResponse,
    summary="Exchange SDP offer for answer",
)
async def exchange_offer(
    request: Request,
    payload: WebRTCOfferRequest,
) -> WebRTCAnswerResponse:
    session_manager = request.app.state.session_manager

    try:
        session_id, answer_sdp = await session_manager.handle_offer(
            sdp=payload.sdp,
            session_id=payload.session_id,
        )
    except KeyError as exc:
        # Explicit "session gone / bad resume id" case -> 404 for client to handle gracefully
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Failed to process WebRTC offer")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process WebRTC offer.",
        ) from exc

    return WebRTCAnswerResponse(session_id=session_id, sdp=answer_sdp)


@router.post(
    "/ice-candidate",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Submit a remote ICE candidate",
)
async def submit_ice_candidate(
    request: Request,
    payload: IceCandidateRequest,
) -> None:
    session_manager = request.app.state.session_manager

    try:
        await session_manager.add_ice_candidate(
            session_id=payload.session_id,
            candidate=payload.candidate,
            sdp_mid=payload.sdp_mid,
            sdp_mline_index=payload.sdp_mline_index,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get(
    "/ice-candidates/{session_id}",
    response_model=IceCandidatesResponse,
    summary="Fetch server-generated ICE candidates (trickle ICE support; drains buffer on read)",
)
async def get_ice_candidates(request: Request, session_id: str) -> IceCandidatesResponse:
    """Clients poll this after setting remote description to receive remote candidates incrementally."""
    session_manager = request.app.state.session_manager
    try:
        # Non-destructive read: client may poll at varying times; duplicates on addIceCandidate are harmless
        cands = session_manager.get_outgoing_ice_candidates(session_id, clear=False)
        return IceCandidatesResponse(candidates=cands)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.delete(
    "/session/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Tear down a signaling session",
)
async def close_session(request: Request, session_id: str) -> None:
    session_manager = request.app.state.session_manager
    metrics: MetricsCollector = request.app.state.metrics
    closed = await session_manager.close_session(session_id)
    if closed:
        metrics.increment_sessions_closed()
    if not closed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown WebRTC session: {session_id}",
        )


@router.delete(
    "/sessions",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Close ALL active WebRTC sessions (dev / test cleanup helper)",
)
async def close_all_sessions(request: Request) -> None:
    """Dev-only helper to clean up accumulated test/demo sessions without server restart."""
    session_manager = request.app.state.session_manager
    metrics: MetricsCollector = request.app.state.metrics
    count = session_manager.active_session_count
    await session_manager.close_all()
    if count:
        metrics.increment_sessions_closed(count)
    logger.info("Closed all active WebRTC sessions (via DELETE /webrtc/sessions)")


@router.get(
    "/sessions",
    response_model=ActiveSessionsResponse,
    summary="List currently active WebRTC sessions (for resume)",
)
async def list_sessions(request: Request) -> ActiveSessionsResponse:
    session_manager = request.app.state.session_manager
    ids = session_manager.list_session_ids()
    details = session_manager.list_sessions_with_details()
    return ActiveSessionsResponse(sessions=ids, count=len(ids), details=details)
