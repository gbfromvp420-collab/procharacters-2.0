"""Contract tests for HTTP provider clients (no external services).

Run: python -m pytest tests/test_contracts.py -q --tb=line
"""

from unittest.mock import MagicMock

import base64

import pytest

from app.core.config import Settings
from app.models.llm import ChatMessage
from app.services.llm.client import OpenAICompatibleLLMClient
from app.services.tts.client import HttpTTSClient
from app.services.video.client import GeneratedFrame, HttpMuseTalkClient
from app.services.video.sync import SyncTimeline


class _MockStreamResponse:
    """Minimal async context manager mimicking httpx stream response."""

    def __init__(self, lines: list[str]) -> None:
        self._lines = lines

    async def __aenter__(self) -> "_MockStreamResponse":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    def raise_for_status(self) -> None:
        return None

    async def aiter_lines(self):
        for line in self._lines:
            yield line


@pytest.mark.asyncio
async def test_http_tts_client_request_shape() -> None:
    settings = Settings(
        tts_provider="http",
        tts_base_url="http://tts.test",
        tts_api_key="tts-key",
        tts_voice="default",
        tts_sample_rate=24000,
        tts_channels=1,
    )
    captured: dict = {}

    pcm = b"\x00\x01" * 120
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.headers = {"content-type": "application/json"}
    mock_response.json.return_value = {
        "audio_b64": base64.b64encode(pcm).decode("ascii"),
        "sample_rate": 24000,
        "channels": 1,
    }

    async def mock_post(path: str, *, json: dict | None = None, **kwargs: object):
        captured["path"] = path
        captured["json"] = json
        return mock_response

    client = HttpTTSClient(settings)
    client._client.post = mock_post  # type: ignore[method-assign]

    result = await client.synthesize("Hello chunk", voice="alice")

    assert captured["path"] == "/synthesize"
    assert captured["json"] == {
        "text": "Hello chunk",
        "voice": "alice",
        "format": "pcm_s16le",
        "sample_rate": 24000,
        "channels": 1,
    }
    assert result.pcm_bytes == pcm
    assert result.sample_rate == 24000
    assert result.channels == 1
    assert result.duration_ms > 0


@pytest.mark.asyncio
async def test_http_musetalk_client_request_and_response_parsing() -> None:
    settings = Settings(
        video_provider="http",
        video_base_url="http://video.test",
        video_api_key="vid-key",
        video_fps=25,
        video_width=512,
        video_height=512,
    )
    captured: dict = {}
    timeline = SyncTimeline(fps=25)

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "frames": [
            {"frame_index": 0, "pts_ms": 0, "frame_b64": "a" * 32},
            {"frame_index": 1, "pts_ms": 40, "frame_b64": "b" * 32},
        ],
        "width": 640,
        "height": 480,
    }

    async def mock_post(path: str, *, json: dict | None = None, **kwargs: object):
        captured["path"] = path
        captured["json"] = json
        return mock_response

    client = HttpMuseTalkClient(settings)
    client._client.post = mock_post  # type: ignore[method-assign]

    result = await client.generate_frames(
        audio_b64="AQID",
        sample_rate=24000,
        channels=1,
        duration_ms=80,
        timeline=timeline,
        avatar_id="avatar-1",
    )

    assert captured["path"] == "/generate"
    assert captured["json"] == {
        "audio_b64": "AQID",
        "sample_rate": 24000,
        "channels": 1,
        "duration_ms": 80,
        "avatar_id": "avatar-1",
        "fps": 25,
        "start_pts_ms": 0,
        "start_frame_index": 0,
    }

    assert len(result.frames) == 2
    assert result.frames[0] == GeneratedFrame(
        frame_index=0, pts_ms=0, frame_b64="a" * 32
    )
    assert result.frames[1] == GeneratedFrame(
        frame_index=1, pts_ms=40, frame_b64="b" * 32
    )
    assert result.width == 640
    assert result.height == 480
    assert timeline.audio_cursor_ms == 80


@pytest.mark.asyncio
async def test_openai_compatible_llm_client_parses_sse_stream() -> None:
    settings = Settings(
        llm_provider="openai_compatible",
        llm_base_url="http://llm.test/v1",
        llm_api_key="sk-test",
        llm_model="test-model",
    )
    captured: dict = {}
    lines = [
        'data: {"choices":[{"index":0,"delta":{"content":"Hel"},"finish_reason":null}]}',
        'data: {"choices":[{"index":0,"delta":{"content":"lo"},"finish_reason":null}]}',
        'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}',
        "data: [DONE]",
    ]

    def mock_stream(
        method: str, path: str, *, json: dict | None = None, **kwargs: object
    ) -> _MockStreamResponse:
        captured["method"] = method
        captured["path"] = path
        captured["json"] = json
        return _MockStreamResponse(lines)

    client = OpenAICompatibleLLMClient(settings)
    client._client.stream = mock_stream  # type: ignore[method-assign]

    messages = [ChatMessage(role="user", content="hi")]
    tokens: list[str] = []
    async for token in client.stream_tokens(
        messages, max_tokens=50, temperature=0.5
    ):
        tokens.append(token)

    assert captured["method"] == "POST"
    assert captured["path"] == "/chat/completions"
    assert captured["json"]["model"] == "test-model"
    assert captured["json"]["stream"] is True
    assert captured["json"]["max_tokens"] == 50
    assert captured["json"]["temperature"] == 0.5
    assert captured["json"]["messages"] == [{"role": "user", "content": "hi"}]
    assert tokens == ["Hel", "lo"]