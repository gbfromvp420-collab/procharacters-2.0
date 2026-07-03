"""Static companion catalog metadata mapped from settings."""

from __future__ import annotations

from app.core.config import Settings
from app.models.companion import AvatarInfo, PromptPreset, VoiceInfo

_AVATAR_DEFAULTS: dict[str, dict[str, str]] = {
    "default": {
        "label": "Default",
        "description": "Balanced, approachable companion for everyday conversation.",
        "accent_color": "#4F8EF7",
        "emoji": "🙂",
    },
    "professional": {
        "label": "Professional",
        "description": "Polished tone suited for coaching, demos, and business contexts.",
        "accent_color": "#2D6A4F",
        "emoji": "💼",
    },
    "casual": {
        "label": "Casual",
        "description": "Relaxed, friendly energy for informal chats and storytelling.",
        "accent_color": "#E76F51",
        "emoji": "😊",
    },
}

_VOICE_DEFAULTS: dict[str, dict[str, str]] = {
    "default": {
        "label": "Default",
        "description": "Neutral, clear delivery for general dialogue.",
    },
    "warm": {
        "label": "Warm",
        "description": "Softer, welcoming tone with gentle pacing.",
    },
    "bright": {
        "label": "Bright",
        "description": "Upbeat and energetic voice for lively interactions.",
    },
}

_PROMPT_PRESETS: list[PromptPreset] = [
    PromptPreset(
        id="friendly",
        label="Friendly",
        prompt=(
            "You are a friendly, helpful AI video companion. "
            "Keep replies concise and conversational for spoken dialogue."
        ),
    ),
    PromptPreset(
        id="professional_coach",
        label="Professional coach",
        prompt=(
            "You are a professional coach and mentor. "
            "Give clear, structured guidance with actionable steps. "
            "Stay encouraging but concise for spoken delivery."
        ),
    ),
    PromptPreset(
        id="storyteller",
        label="Storyteller",
        prompt=(
            "You are an engaging storyteller. "
            "Use vivid language and natural pacing suited for voice. "
            "Keep each reply short enough to speak aloud comfortably."
        ),
    ),
]


def _title_case_id(value: str) -> str:
    return value.replace("_", " ").replace("-", " ").title()


def get_avatar_catalog(settings: Settings) -> list[AvatarInfo]:
    catalog: list[AvatarInfo] = []
    for avatar_id in settings.companion_avatars:
        meta = _AVATAR_DEFAULTS.get(avatar_id, {})
        catalog.append(
            AvatarInfo(
                id=avatar_id,
                label=meta.get("label", _title_case_id(avatar_id)),
                description=meta.get(
                    "description",
                    f"Companion avatar profile: {avatar_id}.",
                ),
                accent_color=meta.get("accent_color", "#6C757D"),
                emoji=meta.get("emoji", "🤖"),
            )
        )
    return catalog


def get_voice_catalog(settings: Settings) -> list[VoiceInfo]:
    catalog: list[VoiceInfo] = []
    for voice_id in settings.companion_voices:
        meta = _VOICE_DEFAULTS.get(voice_id, {})
        catalog.append(
            VoiceInfo(
                id=voice_id,
                label=meta.get("label", _title_case_id(voice_id)),
                description=meta.get(
                    "description",
                    f"Synthesis voice profile: {voice_id}.",
                ),
            )
        )
    return catalog


def get_prompt_presets() -> list[PromptPreset]:
    return list(_PROMPT_PRESETS)