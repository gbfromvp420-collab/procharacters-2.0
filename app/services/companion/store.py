"""Per-session companion state: conversation history and avatar/voice config."""

from dataclasses import dataclass, field

from app.core.config import Settings
from app.models.llm import ChatMessage


@dataclass
class _SessionState:
    messages: list[ChatMessage] = field(default_factory=list)
    avatar_id: str = "default"
    voice: str = "default"
    system_prompt: str = ""


class SessionCompanionStore:
    """In-memory companion state keyed by WebRTC / chat session_id."""

    def __init__(self, settings: Settings | None = None) -> None:
        from app.core.config import get_settings

        self._settings = settings or get_settings()
        self._sessions: dict[str, _SessionState] = {}

    def _default_avatar_id(self) -> str:
        avatars = self._settings.companion_avatars
        return avatars[0] if avatars else self._settings.video_avatar_id

    def _default_voice(self) -> str:
        voices = self._settings.companion_voices
        return voices[0] if voices else self._settings.tts_voice

    def _default_system_prompt(self) -> str:
        return self._settings.companion_system_prompt

    def get_or_create(self, session_id: str) -> _SessionState:
        if session_id not in self._sessions:
            self._sessions[session_id] = _SessionState(
                avatar_id=self._default_avatar_id(),
                voice=self._default_voice(),
                system_prompt=self._default_system_prompt(),
            )
        return self._sessions[session_id]

    def get_config(self, session_id: str) -> dict[str, str]:
        state = self.get_or_create(session_id)
        return {
            "avatar_id": state.avatar_id,
            "voice": state.voice,
            "system_prompt": state.system_prompt,
        }

    def set_config(
        self,
        session_id: str,
        *,
        avatar_id: str | None = None,
        voice: str | None = None,
        system_prompt: str | None = None,
    ) -> dict[str, str]:
        state = self.get_or_create(session_id)
        if avatar_id is not None:
            state.avatar_id = avatar_id
        if voice is not None:
            state.voice = voice
        if system_prompt is not None:
            state.system_prompt = system_prompt
        return self.get_config(session_id)

    def get_messages(self, session_id: str) -> list[ChatMessage]:
        return list(self.get_or_create(session_id).messages)

    def append_turn(
        self,
        session_id: str,
        user_msg: ChatMessage,
        assistant_msg: ChatMessage,
    ) -> None:
        state = self.get_or_create(session_id)
        state.messages.append(user_msg)
        state.messages.append(assistant_msg)
        self._trim_history(state)

    def clear_history(self, session_id: str) -> None:
        state = self.get_or_create(session_id)
        state.messages.clear()

    def remove(self, session_id: str) -> bool:
        return self._sessions.pop(session_id, None) is not None

    def build_llm_messages(
        self,
        session_id: str,
        new_messages: list[ChatMessage],
        *,
        use_memory: bool = True,
    ) -> list[ChatMessage]:
        """Assemble system prompt + stored history + new user/assistant messages."""
        state = self.get_or_create(session_id)
        messages: list[ChatMessage] = [
            ChatMessage(role="system", content=state.system_prompt),
        ]
        if use_memory:
            messages.extend(state.messages)
        messages.extend(new_messages)
        return messages

    def _trim_history(self, state: _SessionState) -> None:
        max_turns = self._settings.companion_max_history_turns
        if max_turns <= 0:
            state.messages.clear()
            return
        max_messages = max_turns * 2
        if len(state.messages) > max_messages:
            state.messages = state.messages[-max_messages:]