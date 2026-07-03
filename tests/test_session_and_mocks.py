"""Simple pytest-style tests covering session_manager (list/create) and mock generation.

These are intentionally lightweight and do not require a running server.
Run: python -m pytest tests/ -q --tb=line
"""

import asyncio
import pytest

from app.core.config import get_settings
from app.models.llm import ChatMessage
from app.services.llm.client import MockLLMClient
from app.services.tts.client import MockTTSClient
from app.services.video.client import MockMuseTalkClient
from app.services.webrtc.session_manager import WebRTCSessionManager


def test_session_manager_create_and_list():
    mgr = WebRTCSessionManager()

    assert mgr.active_session_count == 0
    assert mgr.list_session_ids() == []

    s1 = mgr.create_session()
    assert s1.session_id
    assert mgr.active_session_count == 1
    assert s1.session_id in mgr.list_session_ids()

    s2 = mgr.create_session()
    assert mgr.active_session_count == 2
    ids = mgr.list_session_ids()
    assert len(ids) == 2
    assert s1.session_id in ids and s2.session_id in ids

    # get works
    assert mgr.get_session(s1.session_id) is not None
    assert mgr.get_media_bridge(s2.session_id) is not None


@pytest.mark.asyncio
async def test_session_manager_close():
    mgr = WebRTCSessionManager()
    s = mgr.create_session()
    sid = s.session_id

    closed = await mgr.close_session(sid)
    assert closed is True
    assert mgr.active_session_count == 0
    assert sid not in mgr.list_session_ids()

    # double close is safe
    closed2 = await mgr.close_session(sid)
    assert closed2 is False


@pytest.mark.asyncio
async def test_session_manager_close_all():
    mgr = WebRTCSessionManager()
    mgr.create_session()
    mgr.create_session()
    assert mgr.active_session_count == 2

    await mgr.close_all()
    assert mgr.active_session_count == 0


def test_mock_llm_client_generates_tokens():
    settings = get_settings()
    client = MockLLMClient(settings)

    async def collect():
        tokens = []
        async for tok in client.stream_tokens(
            [ChatMessage(role="user", content="test prompt")],
            max_tokens=20,
            temperature=0.0,
        ):
            tokens.append(tok)
        return tokens

    tokens = asyncio.run(collect())
    assert len(tokens) > 3
    # should contain the echoed user content or model name
    joined = "".join(tokens)
    assert "test prompt" in joined or "mock" in joined.lower()


@pytest.mark.asyncio
async def test_mock_tts_client_produces_audio():
    settings = get_settings()
    client = MockTTSClient(settings)
    audio = await client.synthesize("Hello there, this is a test chunk for tts.")
    assert audio.pcm_bytes
    assert len(audio.pcm_bytes) > 100
    assert audio.duration_ms > 0
    assert audio.sample_rate == settings.tts_sample_rate


@pytest.mark.asyncio
async def test_mock_video_client_produces_frames():
    settings = get_settings()
    client = MockMuseTalkClient(settings)

    # Need a minimal timeline for allocate
    from app.services.video.sync import SyncTimeline
    timeline = SyncTimeline(fps=settings.video_fps)

    result = await client.generate_frames(
        audio_b64="",
        sample_rate=24000,
        channels=1,
        duration_ms=200,
        timeline=timeline,
        avatar_id="default",
    )
    assert result.width == settings.video_width
    assert result.height == settings.video_height
    # At least one frame allocated for 200ms
    assert len(result.frames) >= 1
    assert all(f.frame_b64 for f in result.frames)
