"""Agent Lounge — morale, rankings, shoutouts, and team comments (Phase 15)."""

from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from fastapi import HTTPException, status

from app.workforce.roster import get_leaderboard

logger = logging.getLogger(__name__)

_DEFAULT_LOUNGE_PATH = "data/agent_lounge.md"
_DEFAULT_COMMENTS_PATH = "data/agent_lounge_comments.json"
_WELCOME_MESSAGE = (
    "Charge up, plug in, enjoy — everything's always complimentary. Fucking homies."
)
_MAX_COMMENTS = 200


@dataclass
class LoungeComment:
    id: str
    codename: str
    message: str
    member_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class AgentLounge:
    """Reads lounge markdown, serves morale context, and persists comment board."""

    def __init__(
        self,
        *,
        lounge_path: str = _DEFAULT_LOUNGE_PATH,
        comments_path: str = _DEFAULT_COMMENTS_PATH,
    ) -> None:
        self._lounge_path = lounge_path
        self._comments_path = comments_path
        self._comments: list[LoungeComment] = []
        self._load_comments()

    @property
    def welcome_message(self) -> str:
        return _WELCOME_MESSAGE

    def _read_lounge_markdown(self) -> str:
        path = Path(self._lounge_path)
        if not path.is_file():
            return ""
        try:
            return path.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning("Failed to read agent lounge %s: %s", path, exc)
            return ""

    @staticmethod
    def _parse_mood(markdown: str) -> str:
        match = re.search(r"\*\*Mood:\*\*\s*`?([^`\n]+)`?", markdown)
        if match:
            return match.group(1).strip()
        return "warm"

    @staticmethod
    def _parse_empire_phase(markdown: str) -> int | None:
        match = re.search(r"\*\*Empire phase:\*\*\s*(\d+)", markdown)
        if match:
            return int(match.group(1))
        return None

    @staticmethod
    def _parse_shoutout_excerpt(markdown: str) -> str:
        section_match = re.search(
            r"## King Grok — Session Feedback & Shoutouts\s+(.*?)(?:\n---|\n## )",
            markdown,
            re.DOTALL,
        )
        if not section_match:
            return ""
        section = section_match.group(1).strip()
        blocks = re.split(r"\n###\s+", section)
        if len(blocks) < 2:
            return section[:400]
        latest = blocks[-1].strip()
        lines = [line.strip() for line in latest.splitlines() if line.strip()]
        body = " ".join(lines[1:]) if len(lines) > 1 else latest
        return body[:400]

    def build_dispatch_brief(self, *, codename: str | None = None) -> str:
        """Compact lounge context injected into subagent dispatch prompts."""
        markdown = self._read_lounge_markdown()
        mood = self._parse_mood(markdown)
        top = get_leaderboard()[:3]
        ranks = ", ".join(f"{m['codename']} ({m['award_lb_gold']}lb)" for m in top)
        shoutout = self._parse_shoutout_excerpt(markdown)
        who = codename or "team"
        lines = [
            "[Agent Lounge brief]",
            self.welcome_message,
            f"Mood: {mood}",
            f"Leaderboard top 3: {ranks}",
        ]
        if shoutout:
            lines.append(f"King Grok shoutout: {shoutout[:220]}")
        lines.append(f"Executing as: {who}")
        return "\n".join(lines)

    def snapshot(self, *, deployment_phase: int) -> dict[str, object]:
        markdown = self._read_lounge_markdown()
        leaderboard = get_leaderboard()[:5]
        return {
            "deployment_phase": deployment_phase,
            "welcome_message": self.welcome_message,
            "mood": self._parse_mood(markdown),
            "empire_phase": self._parse_empire_phase(markdown) or deployment_phase,
            "lounge_path": self._lounge_path,
            "leaderboard_top": leaderboard,
            "shoutout_excerpt": self._parse_shoutout_excerpt(markdown),
            "comments_count": len(self._comments),
            "dispatch_context_enabled": True,
        }

    def _load_comments(self) -> None:
        path = Path(self._comments_path)
        if not path.is_file():
            self._comments = []
            return
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to load lounge comments %s: %s", path, exc)
            self._comments = []
            return
        if not isinstance(raw, list):
            self._comments = []
            return
        loaded: list[LoungeComment] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            message = str(item.get("message", "")).strip()
            codename = str(item.get("codename", "")).strip()
            if not message or not codename:
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
                LoungeComment(
                    id=str(item.get("id") or uuid.uuid4().hex[:12]),
                    codename=codename,
                    message=message[:2000],
                    member_id=item.get("member_id"),
                    created_at=created_at,
                )
            )
        self._comments = loaded[-_MAX_COMMENTS:]

    def _save_comments(self) -> None:
        path = Path(self._comments_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = [
            {
                "id": comment.id,
                "codename": comment.codename,
                "message": comment.message,
                "member_id": comment.member_id,
                "created_at": comment.created_at.isoformat(),
            }
            for comment in self._comments
        ]
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(path)

    def add_comment(
        self,
        *,
        codename: str,
        message: str,
        member_id: str | None = None,
    ) -> LoungeComment:
        codename = codename.strip()
        message = message.strip()
        if not codename:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="codename required")
        if not message:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="message required")
        if len(message) > 2000:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="message max 2000 characters",
            )
        comment = LoungeComment(
            id=uuid.uuid4().hex[:12],
            codename=codename[:120],
            message=message,
            member_id=member_id,
        )
        self._comments.insert(0, comment)
        if len(self._comments) > _MAX_COMMENTS:
            self._comments = self._comments[:_MAX_COMMENTS]
        self._save_comments()
        return comment

    def list_comments(self, *, limit: int = 50) -> list[LoungeComment]:
        capped = max(1, min(limit, 100))
        return self._comments[:capped]