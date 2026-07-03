import logging
import uuid
from dataclasses import dataclass, field

from aiortc import RTCIceCandidate, RTCPeerConnection, RTCSessionDescription
from aiortc.sdp import candidate_from_sdp

from app.core.config import Settings
from app.services.webrtc.media_bridge import AvatarMediaBridge

logger = logging.getLogger(__name__)


@dataclass
class WebRTCSession:
    session_id: str
    peer_connection: RTCPeerConnection
    media_bridge: AvatarMediaBridge
    pending_ice_candidates: list[dict[str, str | int | None]] = field(
        default_factory=list
    )
    # Track current states for observability / resume decisions (updated by handlers)
    connection_state: str = "new"
    ice_connection_state: str = "new"
    ice_gathering_state: str = "new"


class WebRTCSessionManager:
    """Manages aiortc peer connections, media bridges, and signaling."""

    def __init__(self, settings: Settings | None = None) -> None:
        from app.core.config import get_settings

        self._settings = settings or get_settings()
        self._sessions: dict[str, WebRTCSession] = {}

    @property
    def ice_servers(self) -> list[dict[str, str | list[str]]]:
        return self._settings.webrtc_ice_servers

    @property
    def active_session_count(self) -> int:
        return len(self._sessions)

    def get_session(self, session_id: str) -> WebRTCSession | None:
        return self._sessions.get(session_id)

    def get_media_bridge(self, session_id: str) -> AvatarMediaBridge | None:
        session = self._sessions.get(session_id)
        return session.media_bridge if session else None

    def list_session_ids(self) -> list[str]:
        return list(self._sessions.keys())

    def list_sessions_with_details(self) -> list[dict[str, str]]:
        """Return richer info for /sessions and health without breaking list API."""
        out: list[dict[str, str]] = []
        for sid, sess in self._sessions.items():
            out.append(
                {
                    "session_id": sid,
                    "connection_state": sess.connection_state,
                    "ice_connection_state": sess.ice_connection_state,
                    "ice_gathering_state": sess.ice_gathering_state,
                }
            )
        return out

    def create_session(self) -> WebRTCSession:
        session_id = str(uuid.uuid4())
        peer_connection = RTCPeerConnection()
        media_bridge = AvatarMediaBridge(session_id, settings=self._settings)
        session = WebRTCSession(
            session_id=session_id,
            peer_connection=peer_connection,
            media_bridge=media_bridge,
        )
        self._sessions[session_id] = session
        self._register_peer_handlers(session)
        logger.debug("Created WebRTC session %s", session_id)
        return session

    async def handle_offer(self, sdp: str, session_id: str | None = None) -> tuple[str, str]:
        """Handle (re)negotiation offer.

        Robust for 2nd+ offers on existing session:
        - Detects bad prior PC state (closed/failed) and recreates PC under same session_id.
        - Re-adds tracks only when needed (after recreate or first time).
        - Supports resume even if prior ICE/connection bad.
        - Queues/flushes pending ICE candidates.
        """
        session: WebRTCSession | None = None
        if session_id and (session := self.get_session(session_id)):
            pc = session.peer_connection
            bad_state = (
                pc is None
                or getattr(pc, "connectionState", "") in ("closed", "failed")
                or getattr(pc, "iceConnectionState", "") in ("closed", "failed")
            )
            if bad_state:
                logger.info(
                    "Session %s has bad PC state (conn=%s ice=%s); recreating for re-negotiation",
                    session_id,
                    getattr(pc, "connectionState", None),
                    getattr(pc, "iceConnectionState", None),
                )
                await self._recreate_peer_connection(session)
            peer_connection = session.peer_connection
        else:
            if session_id:
                # Explicit failure for unknown resume target (no silent new-id create).
                # Client can fallback to /session + fresh connect.
                raise KeyError(f"Unknown WebRTC session for resume/offer: {session_id}")
            session = self.create_session()
            peer_connection = session.peer_connection
            session_id = session.session_id

        # Ensure tracks are attached to bridge + added to *this* PC (handles recreate)
        self._ensure_tracks_on_pc(session)

        try:
            await peer_connection.setRemoteDescription(
                RTCSessionDescription(sdp=sdp, type="offer")
            )
        except Exception as exc:
            # setRemote can fail on bad internal state; one recreate + retry for robustness
            logger.warning(
                "setRemoteDescription failed for %s (%s); recreating PC and retrying",
                session_id,
                exc,
            )
            await self._recreate_peer_connection(session)
            self._ensure_tracks_on_pc(session)
            peer_connection = session.peer_connection
            await peer_connection.setRemoteDescription(
                RTCSessionDescription(sdp=sdp, type="offer")
            )

        await self._flush_pending_candidates(session)

        answer = await peer_connection.createAnswer()
        await peer_connection.setLocalDescription(answer)

        local = peer_connection.localDescription
        if local is None:
            raise RuntimeError("Local SDP answer was not generated.")

        return session_id, local.sdp

    async def add_ice_candidate(
        self,
        session_id: str,
        candidate: str,
        sdp_mid: str | None,
        sdp_mline_index: int | None,
    ) -> None:
        """Add ICE; buffer if remoteDescription not yet set (common during initial offer or resume)."""
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(f"Unknown WebRTC session: {session_id}")

        if not candidate or candidate == "":
            await session.peer_connection.addIceCandidate(None)
            return

        cand_dict: dict[str, str | int | None] = {
            "candidate": candidate,
            "sdp_mid": sdp_mid,
            "sdp_mline_index": sdp_mline_index,
        }
        pc = session.peer_connection
        if getattr(pc, "remoteDescription", None) is None:
            session.pending_ice_candidates.append(cand_dict)
            logger.debug("Buffered ICE candidate for session %s (awaiting remote desc)", session_id)
            return

        await self._apply_ice_candidate(session, cand_dict)

    async def close_session(self, session_id: str) -> bool:
        session = self._sessions.pop(session_id, None)
        if session is None:
            return False

        await session.media_bridge.close(reason="session_closed")
        await session.peer_connection.close()
        logger.debug("Closed WebRTC session %s", session_id)
        return True

    async def close_all(self) -> None:
        session_ids = list(self._sessions.keys())
        for session_id in session_ids:
            await self.close_session(session_id)

    def _ensure_tracks_on_pc(self, session: WebRTCSession) -> None:
        """Attach/create bridge tracks and ensure they are added to current PC.

        Safe for re-negotiation: skips re-add if already present on this PC.
        Re-adds after PC recreate.
        """
        pc = session.peer_connection
        bridge = session.media_bridge
        if not bridge.tracks_attached:
            audio_track, video_track = bridge.attach_tracks()
            pc.addTrack(audio_track)
            pc.addTrack(video_track)
            logger.debug("Attached avatar tracks to session %s", session.session_id)
            return

        # Bridge tracks already created; ensure present on *this* pc instance
        senders = list(pc.getSenders())
        has_audio = any(getattr(s.track, "kind", None) == "audio" for s in senders)
        has_video = any(getattr(s.track, "kind", None) == "video" for s in senders)

        audio_track = getattr(bridge, "_audio_track", None)
        video_track = getattr(bridge, "_video_track", None)

        if not has_audio and audio_track is not None:
            pc.addTrack(audio_track)
            logger.debug("Re-added audio track on PC for session %s", session.session_id)
        if not has_video and video_track is not None:
            pc.addTrack(video_track)
            logger.debug("Re-added video track on PC for session %s", session.session_id)

    async def _recreate_peer_connection(self, session: WebRTCSession) -> None:
        """Close old PC, create fresh one under same session+bridge (for bad-state recovery).

        Tracks are re-added by caller via _ensure_tracks_on_pc.
        Clears pending candidates (will re-arrive or be resent by client).
        """
        old_pc = session.peer_connection
        try:
            await old_pc.close()
        except Exception:
            pass

        new_pc = RTCPeerConnection()
        session.peer_connection = new_pc
        session.connection_state = "new"
        session.ice_connection_state = "new"
        session.ice_gathering_state = "new"
        session.pending_ice_candidates.clear()

        self._register_peer_handlers(session)
        logger.info("Recreated peer connection for session %s", session.session_id)

    async def _apply_ice_candidate(
        self, session: WebRTCSession, cand: dict[str, str | int | None]
    ) -> None:
        candidate = cand.get("candidate") or ""
        if not candidate:
            await session.peer_connection.addIceCandidate(None)
            return
        normalized = str(candidate).removeprefix("candidate:")
        rtc_candidate = candidate_from_sdp(normalized)
        rtc_candidate.sdpMid = cand.get("sdp_mid")
        rtc_candidate.sdpMLineIndex = cand.get("sdp_mline_index")
        await session.peer_connection.addIceCandidate(rtc_candidate)
        logger.debug("Added ICE candidate for session %s", session.session_id)

    async def _flush_pending_candidates(self, session: WebRTCSession) -> None:
        if not session.pending_ice_candidates:
            return
        pending = session.pending_ice_candidates[:]
        session.pending_ice_candidates.clear()
        logger.debug(
            "Flushing %d pending ICE candidates for session %s",
            len(pending),
            session.session_id,
        )
        for c in pending:
            try:
                await self._apply_ice_candidate(session, c)
            except Exception as exc:
                logger.warning(
                    "Failed applying buffered ICE for %s: %s", session.session_id, exc
                )

    def _register_peer_handlers(self, session: WebRTCSession) -> None:
        peer_connection = session.peer_connection
        session_id = session.session_id

        @peer_connection.on("connectionstatechange")
        async def on_connectionstatechange() -> None:
            state = peer_connection.connectionState
            session.connection_state = state
            logger.info("WebRTC session %s connection state: %s", session_id, state)
            if state in {"failed", "closed"}:
                # Only hard close on terminal failure; "disconnected" is often transient/recoverable via re-offer
                await self.close_session(session_id)

        @peer_connection.on("iceconnectionstatechange")
        async def on_iceconnectionstatechange() -> None:
            state = peer_connection.iceConnectionState
            session.ice_connection_state = state
            logger.info("WebRTC session %s ICE state: %s", session_id, state)
            if state == "failed":
                await self.close_session(session_id)

        @peer_connection.on("icegatheringstatechange")
        def on_icegatheringstatechange() -> None:
            state = peer_connection.iceGatheringState
            session.ice_gathering_state = state
            logger.debug("WebRTC session %s ICE gathering state: %s", session_id, state)
