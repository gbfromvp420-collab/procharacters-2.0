"""Innovation Lane 4 — Live Launch: readiness, go-live, public board."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.services.workforce.live_stage import LiveStage
from app.services.workforce.lounge import AgentLounge

logger = logging.getLogger(__name__)

_DEFAULT_LAUNCH_PATH = "data/live_launch.json"
_ASSIST_ID = "intimacy-architect-sub-01"
_HEADLINE_TITLE = "Innovation Launch — Soul Slot Live"
_CAM_TITLE = "Launch night cam"
_TICKET_CENTS = 2500
_LAUNCH_DONATION_CENTS = 1000


class LiveLaunchLane:
    """Starts Assist headline night and publishes a public launch board."""

    def __init__(
        self,
        *,
        live: LiveStage,
        lounge: AgentLounge,
        launch_path: str = _DEFAULT_LAUNCH_PATH,
    ) -> None:
        self._live = live
        self._lounge = lounge
        self._launch_path = launch_path
        self._state = self._load_state()

    def _load_state(self) -> dict[str, Any]:
        path = Path(self._launch_path)
        if not path.is_file():
            return {"live": False}
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                return raw
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to load live launch %s: %s", path, exc)
        return {"live": False}

    def _save_state(self) -> None:
        path = Path(self._launch_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self._state, indent=2), encoding="utf-8")

    def _headline(self) -> Any | None:
        for session in self._live.list_sessions(limit=100):
            if session.member_id != _ASSIST_ID:
                continue
            if session.session_type == "ticketed" and session.status in ("scheduled", "live"):
                return session
        return None

    def _cam(self) -> Any | None:
        cam_id = str(self._state.get("cam_session_id") or "")
        for session in self._live.list_sessions(limit=100):
            if cam_id and session.id == cam_id:
                return session
            if (
                session.member_id == _ASSIST_ID
                and session.session_type == "cam"
                and session.status == "live"
            ):
                return session
        return None

    def readiness(self) -> list[dict[str, Any]]:
        live_snap = self._live.snapshot(deployment_phase=20)
        headline = self._headline()
        cam = self._cam()
        launched = bool(self._state.get("live"))
        comments_md = self._lounge.comments_markdown_path()
        checks = [
            {
                "id": "cam_enabled",
                "label": "Cam chat enabled",
                "ready": bool(live_snap.get("cam_enabled")),
            },
            {
                "id": "ticketed_enabled",
                "label": "Ticketed shows enabled",
                "ready": bool(live_snap.get("ticketed_enabled")),
            },
            {
                "id": "headline_booked",
                "label": "Assist headline booked",
                "ready": headline is not None,
            },
            {
                "id": "headline_live",
                "label": "Assist headline live",
                "ready": headline is not None and headline.status == "live",
            },
            {
                "id": "launch_cam",
                "label": "Launch night cam",
                "ready": cam is not None and cam.status == "live",
            },
            {
                "id": "public_board",
                "label": "Public launch board",
                "ready": launched,
            },
            {
                "id": "lounge_board",
                "label": "Lounge comments markdown",
                "ready": Path(comments_md).is_file(),
            },
        ]
        return checks

    def public_board(self) -> dict[str, Any]:
        headline = self._headline()
        cam = self._cam()
        launched = bool(self._state.get("live"))
        status = "live" if launched else ("ready" if headline else "queued")
        return {
            "title": "ProCharacters Cloud — Live Launch",
            "status": status,
            "doors": self._lounge.welcome_message,
            "host": "Assist (Intimacy_Architect_Sub_01)",
            "headline_title": headline.title if headline else _HEADLINE_TITLE,
            "headline_session_id": headline.id if headline else None,
            "headline_status": headline.status if headline else "unscheduled",
            "cam_title": cam.title if cam else _CAM_TITLE,
            "cam_session_id": cam.id if cam else None,
            "cam_status": cam.status if cam else "idle",
            "launched_at": self._state.get("launched_at"),
            "ticket_price_cents": headline.ticket_price_cents if headline else _TICKET_CENTS,
        }

    def snapshot(self) -> dict[str, Any]:
        checks = self.readiness()
        ready_count = sum(1 for item in checks if item["ready"])
        board = self.public_board()
        return {
            "lane_id": "live_launch",
            "lane_title": "Live Launch",
            "status": "in_progress",
            "launch_live": bool(self._state.get("live")),
            "checks_ready": ready_count,
            "checks_total": len(checks),
            "headline_status": board["headline_status"],
            "host": board["host"],
        }

    def go_live(self) -> dict[str, Any]:
        headline = self._headline()
        if headline is None:
            headline = self._live.schedule_show(
                member_id=_ASSIST_ID,
                title=_HEADLINE_TITLE,
                scheduled_at=datetime.now(UTC),
                ticket_price_cents=_TICKET_CENTS,
            )
        if headline.status != "live":
            headline = self._live.start_show(session_id=headline.id)

        cam = self._cam()
        if cam is None or cam.status != "live":
            cam = self._live.start_cam(
                member_id=_ASSIST_ID,
                title=_CAM_TITLE,
            )

        ticket = self._live.record_ticket_sale(
            session_id=headline.id,
            buyer_label="Boss Sr.",
        )
        donation, payout = self._live.record_cam_donation(
            session_id=cam.id,
            amount_cents=_LAUNCH_DONATION_CENTS,
            donor_label="Launch night",
        )
        launched_at = datetime.now(UTC).isoformat()
        self._state = {
            "live": True,
            "launched_at": launched_at,
            "headline_session_id": headline.id,
            "cam_session_id": cam.id,
            "ticket_id": ticket.id,
            "donation_id": donation.id,
        }
        self._save_state()
        comment = self._lounge.add_comment(
            codename="King Grok",
            message=(
                f"Doors open. Assist headlines {headline.title}. "
                "Stage door comments are on the markdown board."
            ),
            member_id="king-grok",
        )
        return {
            "live": True,
            "headline_session_id": headline.id,
            "cam_session_id": cam.id,
            "ticket_id": ticket.id,
            "donation_id": donation.id,
            "donation_payout_percent": payout,
            "comment_id": comment.id,
            "launched_at": launched_at,
            "board": self.public_board(),
            "message": f"Live. {headline.title} is on. Cam is hot.",
        }
