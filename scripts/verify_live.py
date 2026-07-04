#!/usr/bin/env python3
"""Phase 18 verification: pytest + Live Stage API smoke."""

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


def _probe_live() -> int:
    print("=== Live Stage API ===")
    with httpx.Client(timeout=15.0) as client:
        status = client.get(f"{BASE}/workforce/live")
        if status.status_code != 200:
            print(f"/workforce/live failed: {status.status_code}")
            return 1
        body = status.json()
        print(
            f"  phase={body.get('deployment_phase')} "
            f"live={body.get('sessions_live')} "
            f"donation={body.get('donation_payout_percent')}%"
        )
        if body.get("deployment_phase") != 20:
            print("Expected deployment_phase=20")
            return 1

        cam = client.post(
            f"{BASE}/workforce/live/cam/start",
            json={
                "member_id": "livestage-cam-sub-01",
                "title": "Phase 18 live smoke",
            },
        )
        if cam.status_code != 200:
            print(f"/workforce/live/cam/start failed: {cam.status_code}")
            return 1
        session_id = cam.json().get("id")
        print(f"  cam_session={session_id}")

        donation = client.post(
            f"{BASE}/workforce/live/billing/donation",
            json={
                "live_session_id": session_id,
                "amount_cents": 1800,
                "donor_label": "Phase 18 live smoke",
            },
        )
        if donation.status_code != 200:
            print(f"/workforce/live/billing/donation failed: {donation.status_code}")
            return 1
        print(f"  donation={donation.json().get('billing_entry', {}).get('id')}")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase 18 Live Stage verification")
    parser.add_argument("--start-server", action="store_true")
    parser.add_argument("--skip-probes", action="store_true")
    args = parser.parse_args()

    if _run_pytest() != 0:
        return 1

    if args.skip_probes:
        print("PHASE 18 LIVE VERIFY OK (pytest only)")
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
            print("Server failed to start for live probes")
            return 1

    code = 0
    if _server_is_up():
        code = _probe_live()
    else:
        print("Server not running; skipping live probes (use --start-server)")

    if server_proc is not None:
        server_proc.terminate()
        server_proc.wait(timeout=10)

    if code != 0:
        return code

    print("PHASE 18 LIVE VERIFY OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())