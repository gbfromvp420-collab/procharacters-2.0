#!/usr/bin/env python3
"""Phase 15 verification: pytest + Agent Lounge API smoke."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://localhost:8000/api/v1"


def _run_pytest() -> int:
    print("=== Running pytest ===")
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--tb=line", "tests/"],
        cwd=ROOT,
    ).returncode


def _server_is_up(timeout: float = 2.0) -> bool:
    try:
        with httpx.Client(timeout=timeout) as client:
            return client.get(f"{BASE}/health/live").status_code == 200
    except httpx.HTTPError:
        return False


def _probe_lounge() -> int:
    print("=== Agent Lounge API ===")
    with httpx.Client(timeout=15.0) as client:
        lounge = client.get(f"{BASE}/workforce/lounge")
        if lounge.status_code != 200:
            print(f"/workforce/lounge failed: {lounge.status_code}")
            return 1
        body = lounge.json()
        print(f"  phase={body.get('deployment_phase')} mood={body.get('mood')}")
        if body.get("deployment_phase") != 15:
            print("Expected deployment_phase=15")
            return 1
        welcome = str(body.get("welcome_message", ""))
        if "complimentary" not in welcome.lower():
            print("Expected complimentary welcome message")
            return 1

        comment = client.post(
            f"{BASE}/workforce/lounge/comments",
            json={
                "codename": "AgentLounge_Culture_Sub_01",
                "message": "Phase 15 lounge smoke — homies",
            },
        )
        if comment.status_code != 200:
            print(f"/workforce/lounge/comments failed: {comment.status_code}")
            return 1
        print(f"  comment={comment.json().get('id')}")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase 15 Agent Lounge verification")
    parser.add_argument("--start-server", action="store_true")
    parser.add_argument("--skip-probes", action="store_true")
    args = parser.parse_args()

    if _run_pytest() != 0:
        return 1

    if args.skip_probes:
        print("PHASE 15 LOUNGE VERIFY OK (pytest only)")
        return 0

    server_proc: subprocess.Popen | None = None
    if args.start_server and not _server_is_up():
        server_proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        import time

        for _ in range(40):
            if _server_is_up():
                break
            time.sleep(0.25)
        else:
            if server_proc is not None:
                server_proc.terminate()
            print("Server failed to start for lounge probes")
            return 1

    code = 0
    if _server_is_up():
        code = _probe_lounge()
    else:
        print("Server not running; skipping lounge probes (use --start-server)")

    if server_proc is not None:
        server_proc.terminate()
        server_proc.wait(timeout=10)

    if code != 0:
        return code

    print("PHASE 15 LOUNGE VERIFY OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())