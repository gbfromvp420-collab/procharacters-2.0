#!/usr/bin/env python3
"""
Simple verification script for the mock <-> real provider path in ProCharacters.

Directly exercises the low-level Http*Client / Mock*Client classes (bypasses FastAPI).

Usage examples:
  # Mock (default) - no external services
  python scripts/verify_providers.py

  # Against real http endpoints (set provider + base urls)
  LLM_PROVIDER=openai_compatible LLM_BASE_URL=http://localhost:8001/v1 \
  TTS_PROVIDER=http TTS_BASE_URL=http://localhost:8002 \
  VIDEO_PROVIDER=http VIDEO_BASE_URL=http://localhost:8003 \
    python scripts/verify_providers.py --llm --tts --video

  # Mixed + specific prompt
  python scripts/verify_providers.py --llm --prompt "Tell me a joke in 2 sentences."

It prints:
  - Provider in use
  - Sample output chunks / frames
  - Timings, sizes, events
  - Any validation errors surfaced

Useful as contract smoke test when bringing up RunPod workers.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path

# Ensure we can import app.*
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: F401  (for optional direct testing awareness)

from app.core.config import get_settings
from app.models.llm import ChatMessage
from app.services.llm.client import create_llm_client
from app.services.llm.pipeline import LLMStreamPipeline
from app.services.tts.client import create_tts_client
from app.services.video.client import create_musetalk_client
from app.services.video.sync import SyncTimeline


async def verify_llm(prompt: str = "Hi there, how are you?") -> dict:
    settings = get_settings()
    client = create_llm_client(settings)
    pipeline = LLMStreamPipeline(settings=settings)

    print(f"\n=== LLM ({settings.llm_provider}) ===")
    print(f"  model={settings.llm_model}  base={settings.llm_base_url}")
    messages = [ChatMessage(role="user", content=prompt)]

    tokens = []
    start = time.perf_counter()
    event_count = 0
    error = None

    try:
        async for ev in pipeline.stream_completion(messages, session_id="verify-llm"):
            event_count += 1
            if ev.type == "token":  # type: ignore[attr-defined]
                tokens.append(ev.content)
                if len(tokens) <= 6:
                    print(f"  token[{ev.index}]: {ev.content!r}")
            elif ev.type == "done":
                print(f"  DONE: tokens={ev.token_count} finish={ev.finish_reason}")
            elif ev.type == "error":
                error = ev.message
                print(f"  ERROR: {error}")
    except Exception as exc:
        error = str(exc)
        print(f"  EXCEPTION: {error}")

    dur = (time.perf_counter() - start) * 1000
    full = "".join(tokens)
    print(f"  total_tokens_yielded={len(tokens)}  elapsed={dur:.1f}ms")
    print(f"  preview: {full[:160]!r}{'...' if len(full) > 160 else ''}")
    await client.aclose()
    await pipeline.aclose()
    return {"events": event_count, "tokens": len(tokens), "error": error, "preview": full[:80]}


async def verify_tts(text: str = "Hello world, this is a test of the voice.") -> dict:
    settings = get_settings()
    client = create_tts_client(settings)

    print(f"\n=== TTS ({settings.tts_provider}) ===")
    print(f"  voice={settings.tts_voice} sr={settings.tts_sample_rate} base={settings.tts_base_url}")

    start = time.perf_counter()
    result = None
    error = None
    try:
        # Use low level client directly for exact contract test
        synth = await client.synthesize(text)
        result = {
            "bytes": len(synth.pcm_bytes),
            "duration_ms": synth.duration_ms,
            "sr": synth.sample_rate,
            "ch": synth.channels,
        }
        print(f"  synthesized: {result['bytes']} bytes, {result['duration_ms']}ms, {result['sr']}Hz {result['ch']}ch")
    except Exception as exc:
        error = str(exc)
        print(f"  ERROR: {error}")

    dur = (time.perf_counter() - start) * 1000
    print(f"  elapsed={dur:.1f}ms")
    await client.aclose()
    return {"result": result, "error": error}


async def verify_video(duration_ms: int = 800) -> dict:
    settings = get_settings()
    client = create_musetalk_client(settings)

    print(f"\n=== VIDEO ({settings.video_provider}) ===")
    print(f"  avatar={settings.video_avatar_id} fps={settings.video_fps} base={settings.video_base_url}")

    # Fake audio for the segment (base64 of 1s of silence-ish is fine; http backends ignore content in mock path)
    import base64
    fake_pcm = b"\x00\x00" * (settings.tts_sample_rate // 2)  # ~500ms worth
    audio_b64 = base64.b64encode(fake_pcm).decode("ascii")

    timeline = SyncTimeline(fps=settings.video_fps)

    start = time.perf_counter()
    frames = []
    error = None
    try:
        res = await client.generate_frames(
            audio_b64=audio_b64,
            sample_rate=settings.tts_sample_rate,
            channels=settings.tts_channels,
            duration_ms=duration_ms,
            timeline=timeline,
            avatar_id=settings.video_avatar_id,
        )
        frames = res.frames
        print(f"  received {len(frames)} frames, {res.width}x{res.height}")
        if frames:
            f0 = frames[0]
            print(f"  first: idx={f0.frame_index} pts={f0.pts_ms} b64_len={len(f0.frame_b64)}")
            if len(frames) > 1:
                f1 = frames[-1]
                print(f"  last : idx={f1.frame_index} pts={f1.pts_ms}")
    except Exception as exc:
        error = str(exc)
        print(f"  ERROR: {error}")

    dur = (time.perf_counter() - start) * 1000
    print(f"  elapsed={dur:.1f}ms  timeline_cursor={timeline.audio_cursor_ms}ms")
    await client.aclose()
    return {"frames": len(frames), "error": error}


async def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Verify LLM/TTS/Video clients (mock or http)")
    parser.add_argument("--llm", action="store_true", help="Run LLM verification")
    parser.add_argument("--tts", action="store_true", help="Run TTS verification")
    parser.add_argument("--video", action="store_true", help="Run Video verification")
    parser.add_argument("--all", action="store_true", help="Run all three")
    parser.add_argument("--prompt", default="Hi. Tell me a very short story about robots.", help="Prompt for LLM")
    parser.add_argument("--tts-text", default="This is a realistic length sentence for synthesis timing.", help="Text for TTS")
    parser.add_argument("--video-ms", type=int, default=640, help="Fake audio duration for video gen test")
    args = parser.parse_args()

    settings = get_settings()
    print("ProCharacters Provider Verifier")
    print(f"Settings: LLM={settings.llm_provider} TTS={settings.tts_provider} VIDEO={settings.video_provider}")
    print(f"MOCK_REALISTIC={getattr(settings, 'mock_realistic', True)}")

    run_llm = args.llm or args.all or not (args.llm or args.tts or args.video)
    run_tts = args.tts or args.all or not (args.llm or args.tts or args.video)
    run_video = args.video or args.all

    results = {}
    if run_llm:
        results["llm"] = await verify_llm(args.prompt)
    if run_tts:
        results["tts"] = await verify_tts(args.tts_text)
    if run_video:
        results["video"] = await verify_video(args.video_ms)

    print("\n=== SUMMARY ===")
    for k, v in results.items():
        print(f"  {k}: {v}")

    # Exit non-zero if any errors
    had_error = any(v.get("error") for v in results.values() if isinstance(v, dict))
    if had_error:
        print("\nVerification completed with errors.")
        sys.exit(1)
    print("\nPHASE 12 FORGE OK — provider contracts verified.")


if __name__ == "__main__":
    asyncio.run(main())
