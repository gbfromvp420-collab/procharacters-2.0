from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    app_name: str = "ProCharacters Cloud"
    app_version: str = "0.6.0"
    debug: bool = False

    host: str = "0.0.0.0"
    port: int = 8000

    cors_origins: list[str] = ["*"]

    # WebRTC / signaling (STUN defaults; optional TURN when credentials are set)
    webrtc_ice_servers: list[dict[str, str | list[str]]] = [
        {"urls": "stun:stun.l.google.com:19302"},
    ]
    webrtc_turn_urls: list[str] = []
    webrtc_turn_username: str = ""
    webrtc_turn_credential: str = ""

    # LLM (RunPod / vLLM OpenAI-compatible API)
    # Use "mock" for local; "openai_compatible" for real /v1/chat/completions
    llm_provider: Literal["mock", "openai_compatible"] = "mock"
    llm_base_url: str = "http://localhost:8001/v1"
    llm_api_key: str = ""
    llm_model: str = "meta-llama/Meta-Llama-3-8B-Instruct"
    llm_max_tokens: int = 512
    llm_temperature: float = 0.7
    llm_timeout_seconds: float = 120.0
    llm_mock_token_delay_ms: int = 35

    # TTS (RunPod / remote HTTP synthesis)
    # Use "http" to POST /synthesize (see contract in tts/client.py)
    tts_provider: Literal["mock", "http"] = "mock"
    tts_base_url: str = "http://localhost:8002"
    tts_api_key: str = ""
    tts_voice: str = "default"
    tts_sample_rate: int = 24000
    tts_channels: int = 1
    tts_chunk_min_chars: int = 20
    tts_chunk_max_chars: int = 120
    tts_timeout_seconds: float = 60.0
    tts_mock_chunk_delay_ms: int = 50

    # Video / MuseTalk (RunPod lip-sync)
    # Use "http" to POST /generate (see exact contract in video/client.py)
    video_provider: Literal["mock", "http"] = "mock"
    video_base_url: str = "http://localhost:8003"
    video_api_key: str = ""
    video_avatar_id: str = "default"
    video_fps: int = 25
    video_width: int = 512
    video_height: int = 512
    video_timeout_seconds: float = 120.0
    video_mock_frame_delay_ms: int = 10

    # Provider readiness gate (blocks /chat/perform and /chat/speak when remote providers fail probe)
    provider_gate_enabled: bool = True
    provider_gate_allow_degraded: bool = True

    # Demo / mock realism toggle (affects all three mock clients)
    # When true (default), mocks use variable-length chunks, jittered delays,
    # multi-sentence responses, and spread frame "work" to better simulate real providers.
    mock_realistic: bool = True

    # Companion session memory and persona
    companion_system_prompt: str = (
        "You are a friendly, helpful AI video companion. "
        "Keep replies concise and conversational for spoken dialogue."
    )
    companion_avatars: list[str] = ["default", "professional", "casual"]
    companion_voices: list[str] = ["default", "warm", "bright"]
    companion_max_history_turns: int = 20
    companion_persist_enabled: bool = True
    companion_persist_path: str = "data/companion_sessions.json"
    kgc_policies_path: str = "data/kgc_policies.json"
    companion_session_ttl_hours: int = 72
    companion_relationship_modes: list[str] = [
        "friendly",
        "flirtatious",
        "romantic",
        "deep",
    ]
    companion_summarize_enabled: bool = True
    companion_summarize_after_turns: int = 12
    companion_memory_summary_preview_max: int = 120

    # Optional API key auth for /api/v1/* (GET /health and GET /metrics exempt)
    api_key_enabled: bool = False
    api_key: str = ""

    # In-memory per-IP rate limiting for POST /chat/perform and POST /webrtc/session
    rate_limit_enabled: bool = True
    rate_limit_perform_per_minute: int = 30


@lru_cache
def get_settings() -> Settings:
    return Settings()