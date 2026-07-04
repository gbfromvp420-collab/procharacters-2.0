#!/usr/bin/env python3
"""Innovation Lane 1 verification: pytest + innovation API smoke."""

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
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Innovation Lane 1 verification")
    parser.add_argument("--start-server", action="store_true")
    parser.add_argument("--skip-probes", action="store_true")
    args = parser.parse_args()

    if _run_pytest() != 0:
        return 1

    if args.skip_probes:
        print("INNOVATION LANE 1 VERIFY OK (pytest only)")
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

    print("INNOVATION LANE 1 VERIFY OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())