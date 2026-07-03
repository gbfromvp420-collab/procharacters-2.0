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
        if session_id and (session := self.get_session(session_id)):
            peer_connection = session.peer_connection
        else:
            session = self.create_session()
            peer_connection = session.peer_connection
            session_id = session.session_id

        if not session.media_bridge.tracks_attached:
            audio_track, video_track = session.media_bridge.attach_tracks()
            peer_connection.addTrack(audio_track)
            peer_connection.addTrack(video_track)
            logger.debug("Attached avatar tracks to session %s", session_id)

        await peer_connection.setRemoteDescription(
            RTCSessionDescription(sdp=sdp, type="offer")
        )
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
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(f"Unknown WebRTC session: {session_id}")

        if not candidate or candidate == "":
            await session.peer_connection.addIceCandidate(None)
            return

        normalized = candidate.removeprefix("candidate:")
        rtc_candidate = candidate_from_sdp(normalized)
        rtc_candidate.sdpMid = sdp_mid
        rtc_candidate.sdpMLineIndex = sdp_mline_index
        await session.peer_connection.addIceCandidate(rtc_candidate)
        logger.debug("Added ICE candidate for session %s", session_id)

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

    def _register_peer_handlers(self, session: WebRTCSession) -> None:
        peer_connection = session.peer_connection
        session_id = session.session_id

        @peer_connection.on("connectionstatechange")
        async def on_connectionstatechange() -> None:
            state = peer_connection.connectionState
            logger.info("WebRTC session %s connection state: %s", session_id, state)
            if state in {"failed", "closed"}:
                await self.close_session(session_id)

        @peer_connection.on("iceconnectionstatechange")
        async def on_iceconnectionstatechange() -> None:
            state = peer_connection.iceConnectionState
            logger.info("WebRTC session %s ICE state: %s", session_id, state)
            if state == "failed":
                await self.close_session(session_id)