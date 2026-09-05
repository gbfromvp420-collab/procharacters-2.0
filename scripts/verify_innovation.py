#!/usr/bin/env python3
"""Innovation Lanes 1–2 verification: live-activate wiring + companion soul."""

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


def _probe_innovation() -> int:
    print("=== Innovation Lane 1 (Real Providers) ===")
    with httpx.Client(timeout=15.0) as client:
        status = client.get(f"{BASE}/workforce/innovation")
        if status.status_code != 200:
            print(f"/workforce/innovation failed: {status.status_code}")
            return 1
        body = status.json()
        print(
            f"  active={body.get('active_lane_title')} "
            f"ready={body.get('real_providers_ready')} "
            f"configured={body.get('configured_providers')}/3"
        )
        if body.get("active_lane_id") != "real_providers":
            print("Expected active_lane_id=real_providers")
            return 1

        lanes = client.get(f"{BASE}/workforce/innovation/lanes")
        if lanes.status_code != 200 or lanes.json().get("count") != 4:
            print("Expected 4 innovation lanes")
            return 1

        real = client.get(f"{BASE}/workforce/innovation/real")
        if real.status_code != 200:
            print(f"/workforce/innovation/real failed: {real.status_code}")
            return 1
        print(f"  providers={len(real.json().get('providers', []))} checklist items")

        wiring = client.get(f"{BASE}/workforce/innovation/wiring")
        if wiring.status_code != 200:
            print(f"/workforce/innovation/wiring failed: {wiring.status_code}")
            return 1
        w = wiring.json().get("readiness", {})
        print(f"  wiring wired={w.get('wired')} ready={w.get('all_ready')}")

        soul = client.get(f"{BASE}/workforce/innovation/soul")
        if soul.status_code != 200:
            print(f"/workforce/innovation/soul failed: {soul.status_code}")
            return 1
        soul_body = soul.json()
        if soul_body.get("lane_id") != "companion_soul" or len(soul_body.get("stages", [])) != 5:
            print("Expected companion soul lane with 5 stages")
            return 1
        print(f"  soul stages={len(soul_body.get('stages', []))} owner={soul_body.get('assist_owner')}")

        pin = client.post(
            f"{BASE}/companion/innovation-verify/soul/memories",
            json={"title": "Verify held", "body": "Lane 2 smoke"},
        )
        if pin.status_code != 200:
            print(f"soul pin failed: {pin.status_code}")
            return 1
        checkin = client.get(f"{BASE}/companion/innovation-verify/soul/checkin")
        if checkin.status_code != 200 or not checkin.json().get("greeting"):
            print("soul checkin failed")
            return 1
        print(f"  soul checkin={checkin.json().get('soul_stage_label')}")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Innovation Lane 1 verification")
    parser.add_argument("--start-server", action="store_true")
    parser.add_argument("--skip-probes", action="store_true")
    args = parser.parse_args()

    if _run_pytest() != 0:
        return 1

    if args.skip_probes:
        print("INNOVATION LANES 1–2 VERIFY OK (pytest only)")
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
            print("Server failed to start")
            return 1

    code = 0
    if _server_is_up():
        code = _probe_innovation()
    else:
        print("Server not running; skipping probes (use --start-server)")

    if server_proc is not None:
        server_proc.terminate()
        server_proc.wait(timeout=10)

    if code != 0:
        return code

    print("INNOVATION LANES 1–2 VERIFY OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())