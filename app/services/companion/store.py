"""Per-session companion state: conversation history and avatar/voice config."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from app.core.config import Settings
from app.models.llm import ChatMessage
from app.services.companion.catalog import get_relationship_mode_overlay
from app.services.companion.milestones import (
    BondMilestone,
    check_new_milestone,
    get_milestones_for_ids,
    get_unlocked_milestones,
)
from app.services.companion.persistence import CompanionPersistence
from app.services.companion.summarizer import summarize_turns
from app.services.observability.metrics import MetricsCollector

_ROMANTIC_BOND_MODES = frozenset({"romantic", "flirtatious"})
_SUMMARIZE_BATCH_TURNS = 6


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(ts: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


@dataclass
class _SessionState:
    messages: list[ChatMessage] = field(default_factory=list)
    avatar_id: str = "default"
    voice: str = "default"
    system_prompt: str = ""
    relationship_mode: str = ""
    bond_score: int = 0
    milestones_unlocked: list[str] = field(default_factory=list)
    memory_summary: str = ""
    created_at: str = ""
    last_active_at: str = ""


class SessionCompanionStore:
    """Companion state keyed by WebRTC / chat session_id, optionally persisted to disk."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        metrics: MetricsCollector | None = None,
    ) -> None:
        from app.core.config import get_settings

        self._settings = settings or get_settings()
        self._metrics = metrics
        self._sessions: dict[str, _SessionState] = {}
        self._persistence: CompanionPersistence | None = None
        if self._settings.companion_persist_enabled:
            self._persistence = CompanionPersistence(self._settings.companion_persist_path)
            self._load_from_disk()

    def _default_avatar_id(self) -> str:
        avatars = self._settings.companion_avatars
        return avatars[0] if avatars else self._settings.video_avatar_id

    def _default_voice(self) -> str:
        voices = self._settings.companion_voices
        return voices[0] if voices else self._settings.tts_voice

    def _default_system_prompt(self) -> str:
        return self._settings.companion_system_prompt

    def _load_from_disk(self) -> None:
        if self._persistence is None:
            return
        raw = self._persistence.load()
        for session_id, data in raw.items():
            if not isinstance(data, dict):
                continue
            messages_raw = data.get("messages", [])
            messages: list[ChatMessage] = []
            if isinstance(messages_raw, list):
                for item in messages_raw:
                    if isinstance(item, dict) and "role" in item and "content" in item:
                        messages.append(ChatMessage(**item))
            now = _utc_now_iso()
            created_at = data.get("created_at") or now
            bond_raw = data.get("bond_score", 0)
            try:
                bond_score = max(0, min(100, int(bond_raw)))
            except (TypeError, ValueError):
                bond_score = 0
            milestones_raw = data.get("milestones_unlocked", [])
            milestones_unlocked: list[str] = []
            if isinstance(milestones_raw, list):
                milestones_unlocked = [str(item) for item in milestones_raw if item]
            if not milestones_unlocked and bond_score > 0:
                milestones_unlocked = [
                    milestone.id for milestone in get_unlocked_milestones(bond_score)
                ]
            memory_summary = data.get("memory_summary", "")
            if not isinstance(memory_summary, str):
                memory_summary = ""
            self._sessions[session_id] = _SessionState(
                messages=messages,
                avatar_id=data.get("avatar_id", self._default_avatar_id()),
                voice=data.get("voice", self._default_voice()),
                system_prompt=data.get("system_prompt", self._default_system_prompt()),
                relationship_mode=data.get("relationship_mode", ""),
                bond_score=bond_score,
                milestones_unlocked=milestones_unlocked,
                memory_summary=memory_summary,
                created_at=created_at,
                last_active_at=data.get("last_active_at") or created_at,
            )

    def _serialize_sessions(self) -> dict[str, dict]:
        return {
            session_id: {
                "avatar_id": state.avatar_id,
                "voice": state.voice,
                "system_prompt": state.system_prompt,
                "relationship_mode": state.relationship_mode,
                "bond_score": state.bond_score,
                "milestones_unlocked": list(state.milestones_unlocked),
                "memory_summary": state.memory_summary,
                "messages": [message.model_dump() for message in state.messages],
                "created_at": state.created_at,
                "last_active_at": state.last_active_at,
            }
            for session_id, state in self._sessions.items()
        }

    def _persist(self) -> None:
        if self._persistence is None:
            return
        self._persistence.save(self._serialize_sessions())

    def save_all(self) -> None:
        """Flush all in-memory sessions to disk (no-op when persistence is disabled)."""
        self._persist()

    def get_or_create(self, session_id: str) -> _SessionState:
        if session_id not in self._sessions:
            now = _utc_now_iso()
            self._sessions[session_id] = _SessionState(
                avatar_id=self._default_avatar_id(),
                voice=self._default_voice(),
                system_prompt=self._default_system_prompt(),
                relationship_mode="",
                created_at=now,
                last_active_at=now,
            )
            self._persist()
        return self._sessions[session_id]

    def touch(self, session_id: str) -> None:
        """Update last_active_at for a session (creates session if missing)."""
        state = self.get_or_create(session_id)
        state.last_active_at = _utc_now_iso()
        self._persist()

    def _truncate_memory_preview(self, summary: str) -> str:
        max_len = self._settings.companion_memory_summary_preview_max
        if max_len <= 0 or len(summary) <= max_len:
            return summary
        return summary[: max_len - 3] + "..."

    def get_bond(self, session_id: str) -> int:
        return self.get_or_create(session_id).bond_score

    def _unlock_milestone_if_crossed(
        self,
        state: _SessionState,
        old_score: int,
    ) -> BondMilestone | None:
        milestone = check_new_milestone(old_score, state.bond_score)
        if milestone is None or milestone.id in state.milestones_unlocked:
            return None
        state.milestones_unlocked.append(milestone.id)
        return milestone

    def increment_bond(self, session_id: str, delta: int = 3) -> int:
        state = self.get_or_create(session_id)
        old_score = state.bond_score
        state.bond_score = max(0, min(100, state.bond_score + delta))
        self._unlock_milestone_if_crossed(state, old_score)
        self._persist()
        if self._metrics is not None:
            self._metrics.increment_bond_increments()
        return state.bond_score

    def get_config(self, session_id: str, *, memory_preview: bool = True) -> dict[str, str | int]:
        state = self.get_or_create(session_id)
        memory_summary = (
            self._truncate_memory_preview(state.memory_summary)
            if memory_preview
            else state.memory_summary
        )
        return {
            "avatar_id": state.avatar_id,
            "voice": state.voice,
            "system_prompt": state.system_prompt,
            "relationship_mode": state.relationship_mode,
            "bond_score": state.bond_score,
            "memory_summary": memory_summary,
            "turn_count": len(state.messages) // 2,
            "created_at": state.created_at,
            "last_active_at": state.last_active_at,
        }

    def set_config(
        self,
        session_id: str,
        *,
        avatar_id: str | None = None,
        voice: str | None = None,
        system_prompt: str | None = None,
        relationship_mode: str | None = None,
    ) -> dict[str, str | int]:
        state = self.get_or_create(session_id)
        if avatar_id is not None:
            state.avatar_id = avatar_id
        if voice is not None:
            state.voice = voice
        if system_prompt is not None:
            state.system_prompt = system_prompt
        if relationship_mode is not None:
            state.relationship_mode = relationship_mode
        state.last_active_at = _utc_now_iso()
        self._persist()
        return self.get_config(session_id)

    def get_messages(self, session_id: str) -> list[ChatMessage]:
        return list(self.get_or_create(session_id).messages)

    def append_turn(
        self,
        session_id: str,
        user_msg: ChatMessage,
        assistant_msg: ChatMessage,
    ) -> BondMilestone | None:
        state = self.get_or_create(session_id)
        state.messages.append(user_msg)
        state.messages.append(assistant_msg)
        self._trim_history(state)
        bond_delta = 5 if state.relationship_mode in _ROMANTIC_BOND_MODES else 3
        old_score = state.bond_score
        state.bond_score = max(0, min(100, state.bond_score + bond_delta))
        milestone = self._unlock_milestone_if_crossed(state, old_score)
        self._maybe_summarize(state)
        state.last_active_at = _utc_now_iso()
        self._persist()
        if self._metrics is not None:
            self._metrics.increment_bond_increments()
            self._metrics.increment_companion_turns_saved()
        return milestone

    def clear_history(self, session_id: str) -> None:
        state = self.get_or_create(session_id)
        state.messages.clear()
        state.memory_summary = ""
        state.last_active_at = _utc_now_iso()
        self._persist()

    def remove(self, session_id: str) -> bool:
        removed = self._sessions.pop(session_id, None) is not None
        if removed:
            self._persist()
        return removed

    def list_session_ids(self) -> list[str]:
        return list(self._sessions.keys())

    def list_persisted_sessions(self) -> list[dict[str, str | int]]:
        return [
            {
                "id": session_id,
                "turn_count": len(state.messages) // 2,
                "last_active_at": state.last_active_at,
                "avatar_id": state.avatar_id,
                "bond_score": state.bond_score,
            }
            for session_id, state in self._sessions.items()
        ]

    def prune_stale(self, ttl_hours: int) -> int:
        """Remove sessions whose last_active_at is older than ttl_hours. Returns count removed."""
        if ttl_hours <= 0:
            return 0
        cutoff = datetime.now(timezone.utc) - timedelta(hours=ttl_hours)
        to_remove: list[str] = []
        for session_id, state in self._sessions.items():
            last_active = _parse_iso(state.last_active_at)
            if last_active is None or last_active < cutoff:
                to_remove.append(session_id)
        for session_id in to_remove:
            self._sessions.pop(session_id, None)
        if to_remove:
            self._persist()
        return len(to_remove)

    def build_llm_messages(
        self,
        session_id: str,
        new_messages: list[ChatMessage],
        *,
        use_memory: bool = True,
    ) -> list[ChatMessage]:
        """Assemble system prompt + stored history + new user/assistant messages."""
        state = self.get_or_create(session_id)
        system_content = state.system_prompt.strip()
        overlay = get_relationship_mode_overlay(self._settings, state.relationship_mode)
        if overlay:
            if system_content:
                system_content = f"{system_content}\n\n{overlay}"
            else:
                system_content = overlay
        milestone_overlays = [
            milestone.prompt_overlay
            for milestone in get_milestones_for_ids(state.milestones_unlocked)
        ]
        if milestone_overlays:
            milestone_block = "\n\n".join(milestone_overlays)
            if system_content:
                system_content = f"{system_content}\n\n{milestone_block}"
            else:
                system_content = milestone_block
        messages: list[ChatMessage] = [
            ChatMessage(role="system", content=system_content),
        ]
        memory_summary = state.memory_summary.strip()
        if memory_summary:
            messages.append(
                ChatMessage(
                    role="assistant",
                    content=f"[Memory summary] {memory_summary}",
                )
            )
        if use_memory:
            messages.extend(state.messages)
        messages.extend(new_messages)
        return messages

    def _maybe_summarize(self, state: _SessionState) -> None:
        if not self._settings.companion_summarize_enabled:
            return
        turn_count = len(state.messages) // 2
        if turn_count <= self._settings.companion_summarize_after_turns:
            return
        batch_size = _SUMMARIZE_BATCH_TURNS * 2
        batch = state.messages[:batch_size]
        state.messages = state.messages[batch_size:]
        new_summary = summarize_turns(batch)
        if new_summary:
            if state.memory_summary:
                state.memory_summary = f"{state.memory_summary}\n{new_summary}"
            else:
                state.memory_summary = new_summary

    def _trim_history(self, state: _SessionState) -> None:
        max_turns = self._settings.companion_max_history_turns
        if max_turns <= 0:
            state.messages.clear()
            return
        max_messages = max_turns * 2
        if len(state.messages) > max_messages:
            state.messages = state.messages[-max_messages:]