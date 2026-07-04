"""Live Stage — cam chat, ticketed shows, scheduling, live billing (Phase 18)."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import HTTPException, status

from app.workforce.roster import WORKFORCE_ROSTER

logger = logging.getLogger(__name__)

_DEFAULT_SCHEMA_PATH = "data/live_stage_schema.json"
_DEFAULT_SESSIONS_PATH = "data/live_stage_sessions.json"
_DEFAULT_BILLING_PATH = "data/live_stage_billing.json"
_MAX_SESSIONS = 200
_MAX_BILLING = 500

SessionType = Literal["cam", "ticketed"]
SessionStatus = Literal["scheduled", "live", "ended", "cancelled"]
BillingType = Literal["donation", "ticket", "show_share"]

_DEFAULT_SCHEMA: dict[str, Any] = {
    "cam_chat": {
        "enabled": True,
        "donation_payout_percent": 100.0,
        "min_donation_cents": 100,
    },
    "ticketed_shows": {
        "enabled": True,
        "host_share_percent": 70.0,
        "platform_fee_percent": 30.0,
        "default_ticket_price_cents": 2500,
        "min_ticket_price_cents": 500,
    },
    "scheduling": {
        "lookahead_days": 30,
        "slot_duration_minutes": 30,
    },
    "version": 1,
}


@dataclass
class LiveSession:
    id: str
    session_type: SessionType
    member_id: str
    codename: str
    status: SessionStatus
    title: str
    ticket_price_cents: int
    billing_total_cents: int = 0
    character_id: str | None = None
    viewer_label: str | None = None
    webrtc_session_id: str | None = None
    scheduled_at: datetime | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class BillingEntry:
    id: str
    live_session_id: str
    billing_type: BillingType
    member_id: str
    codename: str
    amount_cents: int
    currency: str
    description: str
    host_payout_cents: int
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class LiveStage:
    """Cam chat sessions, ticketed private shows, and live session billing."""

    def __init__(
        self,
        *,
        schema_path: str = _DEFAULT_SCHEMA_PATH,
        sessions_path: str = _DEFAULT_SESSIONS_PATH,
        billing_path: str = _DEFAULT_BILLING_PATH,
    ) -> None:
        self._schema_path = schema_path
        self._sessions_path = sessions_path
        self._billing_path = billing_path
        self._schema = self._load_or_create_schema()
        self._sessions: list[LiveSession] = []
        self._billing: list[BillingEntry] = []
        self._load_sessions()
        self._load_billing()

    def _load_or_create_schema(self) -> dict[str, Any]:
        path = Path(self._schema_path)
        if path.is_file():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    return raw
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning("Failed to load live stage schema %s: %s", path, exc)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(_DEFAULT_SCHEMA, indent=2), encoding="utf-8")
        return dict(_DEFAULT_SCHEMA)

    def get_schema(self) -> dict[str, Any]:
        return dict(self._schema)

    def _member_lookup(self) -> dict[str, dict[str, Any]]:
        return {member["id"]: member for member in WORKFORCE_ROSTER}

    def _resolve_member(self, member_id: str) -> dict[str, Any]:
        member = self._member_lookup().get(member_id)
        if member is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unknown member {member_id!r}",
            )
        return member

    def _get_session(self, session_id: str) -> LiveSession:
        for session in self._sessions:
            if session.id == session_id:
                return session
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown live session {session_id!r}",
        )

    def _load_sessions(self) -> None:
        path = Path(self._sessions_path)
        if not path.is_file():
            self._sessions = []
            return
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to load live sessions %s: %s", path, exc)
            self._sessions = []
            return
        if not isinstance(raw, list):
            self._sessions = []
            return
        loaded: list[LiveSession] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            session_type = str(item.get("session_type", "")).strip()
            if session_type not in ("cam", "ticketed"):
                continue
            member_id = str(item.get("member_id", "")).strip()
            codename = str(item.get("codename", "")).strip()
            if not member_id or not codename:
                continue
            status_raw = str(item.get("status", "scheduled"))
            if status_raw not in ("scheduled", "live", "ended", "cancelled"):
                status_raw = "scheduled"

            def _parse_dt(key: str) -> datetime | None:
                raw_val = item.get(key)
                if not raw_val:
                    return None
                try:
                    return datetime.fromisoformat(str(raw_val).replace("Z", "+00:00"))
                except ValueError:
                    return None

            try:
                ticket_price = int(item.get("ticket_price_cents", 0))
                billing_total = int(item.get("billing_total_cents", 0))
            except (TypeError, ValueError):
                continue
            created_raw = item.get("created_at")
            try:
                created_at = (
                    datetime.fromisoformat(str(created_raw).replace("Z", "+00:00"))
                    if created_raw
                    else datetime.now(UTC)
                )
            except ValueError:
                created_at = datetime.now(UTC)
            loaded.append(
                LiveSession(
                    id=str(item.get("id") or uuid.uuid4().hex[:12]),
                    session_type=session_type,  # type: ignore[arg-type]
                    member_id=member_id,
                    codename=codename[:120],
                    status=status_raw,  # type: ignore[arg-type]
                    title=str(item.get("title", ""))[:200],
                    ticket_price_cents=max(0, ticket_price),
                    billing_total_cents=max(0, billing_total),
                    character_id=item.get("character_id"),
                    viewer_label=item.get("viewer_label"),
                    webrtc_session_id=item.get("webrtc_session_id"),
                    scheduled_at=_parse_dt("scheduled_at"),
                    started_at=_parse_dt("started_at"),
                    ended_at=_parse_dt("ended_at"),
                    created_at=created_at,
                )
            )
        self._sessions = loaded[-_MAX_SESSIONS:]

    def _save_sessions(self) -> None:
        path = Path(self._sessions_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = [
            {
                "id": session.id,
                "session_type": session.session_type,
                "member_id": session.member_id,
                "codename": session.codename,
                "status": session.status,
                "title": session.title,
                "ticket_price_cents": session.ticket_price_cents,
                "billing_total_cents": session.billing_total_cents,
                "character_id": session.character_id,
                "viewer_label": session.viewer_label,
                "webrtc_session_id": session.webrtc_session_id,
                "scheduled_at": session.scheduled_at.isoformat() if session.scheduled_at else None,
                "started_at": session.started_at.isoformat() if session.started_at else None,
                "ended_at": session.ended_at.isoformat() if session.ended_at else None,
                "created_at": session.created_at.isoformat(),
            }
            for session in self._sessions
        ]
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(path)

    def _load_billing(self) -> None:
        path = Path(self._billing_path)
        if not path.is_file():
            self._billing = []
            return
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to load live billing %s: %s", path, exc)
            self._billing = []
            return
        if not isinstance(raw, list):
            self._billing = []
            return
        loaded: list[BillingEntry] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            billing_type = str(item.get("billing_type", "")).strip()
            if billing_type not in ("donation", "ticket", "show_share"):
                continue
            try:
                amount_cents = int(item.get("amount_cents", 0))
                host_payout = int(item.get("host_payout_cents", 0))
            except (TypeError, ValueError):
                continue
            if amount_cents <= 0:
                continue
            created_raw = item.get("created_at")
            try:
                created_at = (
                    datetime.fromisoformat(str(created_raw).replace("Z", "+00:00"))
                    if created_raw
                    else datetime.now(UTC)
                )
            except ValueError:
                created_at = datetime.now(UTC)
            loaded.append(
                BillingEntry(
                    id=str(item.get("id") or uuid.uuid4().hex[:12]),
                    live_session_id=str(item.get("live_session_id", "")),
                    billing_type=billing_type,  # type: ignore[arg-type]
                    member_id=str(item.get("member_id", "")),
                    codename=str(item.get("codename", ""))[:120],
                    amount_cents=amount_cents,
                    currency=str(item.get("currency", "USD"))[:8],
                    description=str(item.get("description", ""))[:500],
                    host_payout_cents=host_payout,
                    created_at=created_at,
                )
            )
        self._billing = loaded[-_MAX_BILLING:]

    def _save_billing(self) -> None:
        path = Path(self._billing_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = [
            {
                "id": entry.id,
                "live_session_id": entry.live_session_id,
                "billing_type": entry.billing_type,
                "member_id": entry.member_id,
                "codename": entry.codename,
                "amount_cents": entry.amount_cents,
                "currency": entry.currency,
                "description": entry.description,
                "host_payout_cents": entry.host_payout_cents,
                "created_at": entry.created_at.isoformat(),
            }
            for entry in self._billing
        ]
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(path)

    def _record_billing(
        self,
        *,
        live_session: LiveSession,
        billing_type: BillingType,
        amount_cents: int,
        description: str,
        host_payout_cents: int,
        currency: str = "USD",
    ) -> BillingEntry:
        entry = BillingEntry(
            id=uuid.uuid4().hex[:12],
            live_session_id=live_session.id,
            billing_type=billing_type,
            member_id=live_session.member_id,
            codename=live_session.codename,
            amount_cents=amount_cents,
            currency=currency[:8],
            description=description[:500],
            host_payout_cents=host_payout_cents,
        )
        self._billing.insert(0, entry)
        live_session.billing_total_cents += host_payout_cents
        if len(self._billing) > _MAX_BILLING:
            self._billing = self._billing[:_MAX_BILLING]
        self._save_billing()
        self._save_sessions()
        return entry

    def start_cam(
        self,
        *,
        member_id: str,
        title: str | None = None,
        viewer_label: str | None = None,
        webrtc_session_id: str | None = None,
        character_id: str | None = None,
    ) -> LiveSession:
        cam = self._schema.get("cam_chat", {})
        if isinstance(cam, dict) and not cam.get("enabled", True):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cam chat disabled")
        member = self._resolve_member(member_id)
        now = datetime.now(UTC)
        session = LiveSession(
            id=uuid.uuid4().hex[:12],
            session_type="cam",
            member_id=member_id,
            codename=member["codename"],
            status="live",
            title=(title or f"Cam — {member['codename']}")[:200],
            ticket_price_cents=0,
            character_id=character_id,
            viewer_label=viewer_label,
            webrtc_session_id=webrtc_session_id,
            started_at=now,
        )
        self._sessions.insert(0, session)
        if len(self._sessions) > _MAX_SESSIONS:
            self._sessions = self._sessions[:_MAX_SESSIONS]
        self._save_sessions()
        return session

    def end_session(self, *, session_id: str) -> LiveSession:
        session = self._get_session(session_id)
        if session.status == "ended":
            return session
        if session.status == "cancelled":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Session cancelled")
        session.status = "ended"
        session.ended_at = datetime.now(UTC)
        self._save_sessions()
        return session

    def schedule_show(
        self,
        *,
        member_id: str,
        title: str,
        scheduled_at: datetime,
        ticket_price_cents: int | None = None,
        character_id: str | None = None,
    ) -> LiveSession:
        shows = self._schema.get("ticketed_shows", {})
        if isinstance(shows, dict) and not shows.get("enabled", True):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ticketed shows disabled")
        member = self._resolve_member(member_id)
        title = title.strip()
        if not title:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="title required")
        default_price = int(shows.get("default_ticket_price_cents", 2500)) if isinstance(shows, dict) else 2500
        min_price = int(shows.get("min_ticket_price_cents", 500)) if isinstance(shows, dict) else 500
        price = ticket_price_cents if ticket_price_cents is not None else default_price
        if price < min_price:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"ticket_price_cents must be >= {min_price}",
            )
        session = LiveSession(
            id=uuid.uuid4().hex[:12],
            session_type="ticketed",
            member_id=member_id,
            codename=member["codename"],
            status="scheduled",
            title=title[:200],
            ticket_price_cents=price,
            character_id=character_id,
            scheduled_at=scheduled_at,
        )
        self._sessions.insert(0, session)
        if len(self._sessions) > _MAX_SESSIONS:
            self._sessions = self._sessions[:_MAX_SESSIONS]
        self._save_sessions()
        return session

    def start_show(self, *, session_id: str) -> LiveSession:
        session = self._get_session(session_id)
        if session.session_type != "ticketed":
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Not a ticketed show")
        if session.status not in ("scheduled", "live"):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Cannot start show in {session.status}")
        session.status = "live"
        session.started_at = datetime.now(UTC)
        self._save_sessions()
        return session

    def record_cam_donation(
        self,
        *,
        session_id: str,
        amount_cents: int,
        donor_label: str | None = None,
        currency: str = "USD",
    ) -> tuple[BillingEntry, float]:
        cam = self._schema.get("cam_chat", {})
        payout_percent = float(cam.get("donation_payout_percent", 100.0)) if isinstance(cam, dict) else 100.0
        min_donation = int(cam.get("min_donation_cents", 100)) if isinstance(cam, dict) else 100
        if amount_cents < min_donation:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"amount_cents must be >= {min_donation}",
            )
        session = self._get_session(session_id)
        if session.session_type != "cam":
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Not a cam session")
        if session.status != "live":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cam session not live")
        host_payout = int(amount_cents * (payout_percent / 100.0))
        donor = (donor_label or "anonymous").strip()[:80]
        entry = self._record_billing(
            live_session=session,
            billing_type="donation",
            amount_cents=amount_cents,
            description=f"Cam donation from {donor}",
            host_payout_cents=host_payout,
            currency=currency,
        )
        return entry, payout_percent

    def record_ticket_sale(
        self,
        *,
        session_id: str,
        buyer_label: str | None = None,
        amount_cents: int | None = None,
        currency: str = "USD",
    ) -> BillingEntry:
        shows = self._schema.get("ticketed_shows", {})
        host_share = float(shows.get("host_share_percent", 70.0)) if isinstance(shows, dict) else 70.0
        session = self._get_session(session_id)
        if session.session_type != "ticketed":
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Not a ticketed show")
        if session.status not in ("scheduled", "live"):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Show not bookable")
        gross = amount_cents if amount_cents is not None else session.ticket_price_cents
        if gross <= 0:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid ticket amount")
        host_payout = int(gross * (host_share / 100.0))
        buyer = (buyer_label or "fan").strip()[:80]
        return self._record_billing(
            live_session=session,
            billing_type="ticket",
            amount_cents=gross,
            description=f"Ticket sale — {session.title} — buyer {buyer}",
            host_payout_cents=host_payout,
            currency=currency,
        )

    def list_sessions(self, *, limit: int = 50) -> list[LiveSession]:
        capped = max(1, min(limit, 100))
        return self._sessions[:capped]

    def list_billing(self, *, limit: int = 50) -> list[BillingEntry]:
        capped = max(1, min(limit, 100))
        return self._billing[:capped]

    def snapshot(self, *, deployment_phase: int) -> dict[str, object]:
        cam = self._schema.get("cam_chat", {})
        shows = self._schema.get("ticketed_shows", {})
        live_count = sum(1 for s in self._sessions if s.status == "live")
        scheduled_count = sum(1 for s in self._sessions if s.status == "scheduled")
        billing_total = sum(entry.host_payout_cents for entry in self._billing)
        return {
            "deployment_phase": deployment_phase,
            "cam_enabled": bool(cam.get("enabled", True)) if isinstance(cam, dict) else True,
            "ticketed_enabled": bool(shows.get("enabled", True)) if isinstance(shows, dict) else True,
            "donation_payout_percent": float(cam.get("donation_payout_percent", 100.0))
            if isinstance(cam, dict)
            else 100.0,
            "host_share_percent": float(shows.get("host_share_percent", 70.0))
            if isinstance(shows, dict)
            else 70.0,
            "sessions_total": len(self._sessions),
            "sessions_live": live_count,
            "sessions_scheduled": scheduled_count,
            "billing_entries": len(self._billing),
            "billing_total_cents": billing_total,
            "sessions_path": self._sessions_path,
            "billing_path": self._billing_path,
        }