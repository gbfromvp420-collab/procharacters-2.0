#!/usr/bin/env python3
"""
Practical verification and demo script for ProCharacters 2.0.

- Starts the server (if needed / --start-server) or assumes running on localhost:8000
- Cleans up test sessions via DELETE /webrtc/sessions
- Creates a WebRTC session (shows create flow)
- Performs WebRTC signaling using aiortc (if available) to attach tracks / simulate connect
- Calls /chat/perform with a prompt (using session_id)
- Streams SSE and counts event types: token, audio, video_frame, done*, tts_*, video_*, error*
- Demonstrates "resume" flow: lists active sessions then re-uses the same session_id for a 2nd perform
- Prints summary counts and basic pipeline verification

Prioritizes runnable end-to-end verification of the LLM->TTS->Video pipeline + session reuse.

Run (with server deps):
  python -m venv .venv && source .venv/bin/activate
  pip install -r requirements.txt
  python scripts/demo.py
  # or with auto-start:
  python scripts/demo.py --start-server

Or after `uvicorn app.main:app --port 8000` is running in another terminal:
  python scripts/demo.py
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import subprocess
import sys
import time
from collections import Counter
from contextlib import suppress
from typing import Any

import httpx

BASE = os.environ.get("DEMO_BASE_URL", "http://localhost:8000/api/v1")
HEALTH_URL = f"{BASE}/health"
SESSIONS_URL = f"{BASE}/webrtc/sessions"
SESSION_URL = f"{BASE}/webrtc/session"
OFFER_URL = f"{BASE}/webrtc/offer"
PERFORM_URL = f"{BASE}/chat/perform"
CLOSE_ALL_URL = f"{BASE}/webrtc/sessions"

DEFAULT_PROMPT = "Hello, tell me a very short fun fact about AI avatars."
RESUME_PROMPT = "Thanks! Now give one more short sentence continuing the thought."

# Event types we care about from SSE (see models/ and chat.py)
INTERESTING_TYPES = (
    "token",
    "audio",
    "video_frame",
    "done",
    "tts_done",
    "video_done",
    "error",
    "tts_error",
    "video_error",
)


def log(msg: str) -> None:
    print(f"[demo] {msg}", flush=True)


async def wait_for_server(timeout: float = 15.0, interval: float = 0.3) -> bool:
    start = time.time()
    async with httpx.AsyncClient(timeout=2.0) as client:
        while time.time() - start < timeout:
            try:
                r = await client.get(HEALTH_URL)
                if r.status_code == 200:
                    data = r.json()
                    log(f"Server healthy: {data.get('service')} v{data.get('version')} (sessions={data.get('active_webrtc_sessions')})")
                    return True
            except Exception:
                pass
            await asyncio.sleep(interval)
    return False


def start_server_in_bg() -> subprocess.Popen | None:
    """Start uvicorn without reload for reliable demo shutdown."""
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
        "--no-reload",
        "--log-level",
        "warning",
    ]
    log(f"Starting server in background: {' '.join(cmd)}")
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        return proc
    except Exception as exc:
        log(f"Failed to start server: {exc}")
        return None


async def cleanup_sessions() -> None:
    """Use the dev cleanup endpoint to remove accumulated test sessions."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        with suppress(Exception):
            await client.delete(CLOSE_ALL_URL)
            log("Cleaned up all WebRTC sessions (DELETE /webrtc/sessions)")


async def create_session() -> str:
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.post(SESSION_URL)
        r.raise_for_status()
        data = r.json()
        sid = data["session_id"]
        log(f"Created session: {sid[:8]} (full: {sid})")
        return sid


async def do_webrtc_signaling(session_id: str) -> bool:
    """Optional: perform minimal WebRTC signaling using aiortc (if installed).
    This exercises /offer and causes server to attach avatar tracks to the session/bridge.
    """
    try:
        from aiortc import RTCPeerConnection, RTCSessionDescription  # type: ignore
    except Exception as exc:
        log(f"aiortc not importable ({exc}); skipping WebRTC signaling step (still OK for pipeline demo).")
        return False

    pc: RTCPeerConnection | None = None
    try:
        pc = RTCPeerConnection()
        # recvonly like the browser client
        pc.addTransceiver("audio", direction="recvonly")
        pc.addTransceiver("video", direction="recvonly")

        offer = await pc.createOffer()
        await pc.setLocalDescription(offer)

        payload = {
            "session_id": session_id,
            "sdp": pc.localDescription.sdp,
            "type": "offer",
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(OFFER_URL, json=payload)
            r.raise_for_status()
            answer = r.json()

        await pc.setRemoteDescription(
            RTCSessionDescription(sdp=answer["sdp"], type="answer")
        )
        log("WebRTC signaling succeeded (offer/answer exchanged; tracks attached on server).")
        return True
    except Exception as exc:
        log(f"WebRTC signaling step failed (non-fatal): {exc}")
        return False
    finally:
        if pc is not None:
            with suppress(Exception):
                await pc.close()


async def stream_perform_and_count(
    session_id: str,
    prompt: str,
    label: str = "perform",
) -> tuple[Counter, int, dict[str, Any]]:
    """POST to /chat/perform, parse SSE events, return (type_counter, total_events, last_done_or_error).

    Also captures video_frame pts_ms to verify continuous PTS across multi-turn performs
    (no restart to ~0 on second perform; critical for pacing/lip-sync).
    """
    counters: Counter = Counter()
    total = 0
    summary: dict[str, Any] = {"prompt": prompt}
    last_event: dict[str, Any] | None = None
    video_pts: list[int] = []

    payload = {
        "session_id": session_id,
        "messages": [{"role": "user", "content": prompt}],
    }

    log(f"Calling /chat/perform ({label}) with session {session_id[:8]}… prompt={prompt!r}")

    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream("POST", PERFORM_URL, json=payload) as resp:
            resp.raise_for_status()
            buffer = ""
            async for line in resp.aiter_lines():
                if not line:
                    # end of one SSE message
                    if buffer.strip():
                        data = buffer.strip()
                        if data.startswith("data:"):
                            data = data[5:].strip()
                        try:
                            event = json.loads(data)
                            etype = event.get("type", "unknown")
                            counters[etype] += 1
                            total += 1
                            last_event = event

                            # quick progress for tokens
                            if etype == "token":
                                content = event.get("content", "")
                                if content and len(summary.get("first_tokens", "")) < 60:
                                    summary.setdefault("first_tokens", "")
                                    summary["first_tokens"] += content

                            # Capture pts for multi-turn continuity verification (video pts must not reset)
                            if etype == "video_frame" and isinstance(event.get("pts_ms"), int):
                                video_pts.append(event["pts_ms"])
                        except json.JSONDecodeError:
                            pass
                    buffer = ""
                    continue
                buffer += line + "\n"

            # flush final
            if buffer.strip():
                data = buffer.strip()
                if data.startswith("data:"):
                    data = data[5:].strip()
                try:
                    event = json.loads(data)
                    etype = event.get("type", "unknown")
                    counters[etype] += 1
                    total += 1
                    last_event = event
                    if etype == "video_frame" and isinstance(event.get("pts_ms"), int):
                        video_pts.append(event["pts_ms"])
                except Exception:
                    pass

    # normalize interesting types + group "done" variants
    for k in list(counters.keys()):
        if k.endswith("_done") or k == "done":
            counters["done_variants"] += counters.pop(k)

    # also capture raw done counts for report
    summary["counters"] = dict(counters)
    summary["total_events"] = total
    summary["last_event_type"] = last_event.get("type") if last_event else None
    summary["video_pts"] = video_pts
    summary["min_video_pts"] = min(video_pts) if video_pts else -1
    summary["max_video_pts"] = max(video_pts) if video_pts else -1

    if last_event and last_event.get("type") in {"error", "tts_error", "video_error"}:
        summary["error"] = last_event.get("message")

    log(f"  {label}: received {total} events. Top types: {dict(counters.most_common(6))}")
    if video_pts:
        log(f"    {label} video_pts: min={summary['min_video_pts']} max={summary['max_video_pts']} count={len(video_pts)}")
    return counters, total, summary


async def list_sessions() -> list[str]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(SESSIONS_URL)
        r.raise_for_status()
        data = r.json()
        ids = data.get("sessions", [])
        log(f"Active sessions ({data.get('count')}): {[s[:8] for s in ids]}")
        return ids


async def run_demo(args: argparse.Namespace) -> int:
    started_proc: subprocess.Popen | None = None
    exit_code = 0

    try:
        # 1. Ensure server
        up = await wait_for_server(timeout=1.5)
        if not up:
            if args.start_server:
                started_proc = start_server_in_bg()
                if started_proc is None:
                    log("ERROR: could not launch server")
                    return 1
                log("Waiting for server to become healthy…")
                up = await wait_for_server(timeout=20.0)
            else:
                log("Server not responding on " + BASE)
                log("Tip: run `uvicorn app.main:app --reload` in another shell, or use --start-server")
                return 1

        if not up:
            log("ERROR: server never became healthy")
            return 1

        # 2. Cleanup any old test sessions (prevents accumulation)
        await cleanup_sessions()

        # 3. Create session
        session_id = await create_session()

        # 4. Optional signaling (shows aiortc usage + activates bridge tracks)
        if not args.no_signaling:
            await do_webrtc_signaling(session_id)

            # Exercise re-negotiation (2nd+ offer on *existing* session) to test hardened handle_offer,
            # track attach logic, PC recreate, pending ICE etc.
            log("Re-using same session_id for 2nd signaling (re-negotiation test)...")
            await do_webrtc_signaling(session_id)

        # 5. First perform (pipeline run)
        c1, t1, s1 = await stream_perform_and_count(session_id, DEFAULT_PROMPT, "first")

        # 6. Show resume flow: list + re-use session for second perform
        active = await list_sessions()
        if session_id not in active:
            log("WARNING: session disappeared after first perform (unexpected in mock)")
        else:
            log("Session still active → resume flow test")

        c2, t2, s2 = await stream_perform_and_count(session_id, RESUME_PROMPT, "resume")

        # 7. Final list + summary
        await list_sessions()
        await cleanup_sessions()  # tidy up

        # Report
        print("\n" + "=" * 60)
        print("DEMO SUMMARY (pipeline + resume verification)")
        print("=" * 60)
        print(f"Session ID used: {session_id}")
        print(f"First perform events:  {t1}  types={s1['counters']}")
        print(f"Resume perform events: {t2}  types={s2['counters']}")
        print(f"First tokens sample: {s1.get('first_tokens', '')[:80]!r}")
        print(f"Video PTS continuity (multi-turn): first_max={s1.get('max_video_pts')}, resume_min={s2.get('min_video_pts')}")
        print()

        # Success criteria: saw some tokens, audio or video in at least one run (mock always produces)
        saw_pipeline = False
        for c in (c1, c2):
            if c.get("token", 0) > 0 or c.get("audio", 0) > 0 or c.get("video_frame", 0) > 0:
                saw_pipeline = True
                break

        # PTS continuity check for multi-turn/resume (new performs must NOT restart pts~0)
        # With fix: second perform video pts start where first's audio/video left off (continuous).
        continuity_ok = True
        max1 = s1.get("max_video_pts", -1)
        min2 = s2.get("min_video_pts", -1)
        if max1 > 0 and min2 >= 0:
            if min2 < max1 - 200:  # tolerate minor offset from frame alloc rounding; restart would give min2~0
                continuity_ok = False
                log("PTS CONTINUITY WARNING: resume video pts appear to have restarted (min2 << max1)")

        if saw_pipeline and t1 > 0 and t2 > 0 and continuity_ok:
            print("✅ SUCCESS: pipeline produced events and resume (same session_id) worked.")
            print("   Observed event types include token/audio/video_frame/done flows.")
            print("   PTS continuity across performs: OK (no restart).")
        else:
            print("⚠️  Partial: check output. No tokens/audio/frames seen or one perform empty or PTS restarted.")
            exit_code = 2

        if s1.get("error") or s2.get("error"):
            print("ERRORS seen:", s1.get("error") or s2.get("error"))
            exit_code = 3

        print("=" * 60 + "\n")
        return exit_code

    except KeyboardInterrupt:
        log("Interrupted by user")
        return 130
    except Exception as exc:
        log(f"UNEXPECTED ERROR in demo: {exc}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        # Always attempt final cleanup
        with suppress(Exception):
            await cleanup_sessions()
        if started_proc:
            log("Terminating demo-started server…")
            started_proc.terminate()
            with suppress(Exception):
                started_proc.wait(timeout=3)
            if started_proc.poll() is None:
                started_proc.kill()


def main() -> None:
    parser = argparse.ArgumentParser(description="ProCharacters 2.0 mock demo + verification")
    parser.add_argument(
        "--start-server",
        action="store_true",
        help="Start uvicorn (no-reload) automatically if not already running",
    )
    parser.add_argument(
        "--no-signaling",
        action="store_true",
        help="Skip the aiortc WebRTC signaling step",
    )
    args = parser.parse_args()

    # Make Ctrl-C clean
    if sys.platform != "win32":
        signal.signal(signal.SIGINT, lambda *_: sys.exit(130))

    try:
        code = asyncio.run(run_demo(args))
    except Exception as e:
        log(f"Fatal: {e}")
        code = 1
    sys.exit(code)


if __name__ == "__main__":
    main()
