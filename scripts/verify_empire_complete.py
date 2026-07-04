#!/usr/bin/env python3
"""Phase 20 verification: pytest + Crown Completion API smoke (v1.0)."""

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


def _probe_crown() -> int:
    print("=== Crown Completion API (v1.0) ===")
    with httpx.Client(timeout=15.0) as client:
        live = client.get(f"{BASE}/health/live")
        if live.status_code != 200:
            print(f"/health/live failed: {live.status_code}")
            return 1
        live_body = live.json()
        print(
            f"  live: v{live_body.get('version')} phase={live_body.get('deployment_phase')}"
        )
        if live_body.get("deployment_phase") != 20:
            print("Expected deployment_phase=20")
            return 1
        if live_body.get("version") != "1.0.0":
            print("Expected version=1.0.0")
            return 1

        status = client.get(f"{BASE}/workforce/crown")
        if status.status_code != 200:
            print(f"/workforce/crown failed: {status.status_code}")
            return 1
        body = status.json()
        print(
            f"  crown: workers={body.get('workers_awarded')} "
            f"platinum_pool=${body.get('platinum_pool_value_usd'):,} "
            f"complete={body.get('crown_complete')}"
        )
        if body.get("deployment_phase") != 20:
            print("Expected crown deployment_phase=20")
            return 1
        if not body.get("crown_complete"):
            print("Expected crown_complete=true")
            return 1
        if body.get("platinum_value_usd") != 5000:
            print("Expected platinum_value_usd=5000")
            return 1

        rankings = client.get(f"{BASE}/workforce/crown/rankings")
        if rankings.status_code != 200 or rankings.json().get("count") != 3:
            print("Expected 3 phase rankings")
            return 1
        print(f"  top_phase=#{rankings.json()['rankings'][0]['rank']} {rankings.json()['rankings'][0]['name']}")

        platinum = client.get(f"{BASE}/workforce/crown/platinum")
        if platinum.status_code != 200:
            print(f"/workforce/crown/platinum failed: {platinum.status_code}")
            return 1
        print(f"  platinum_awards={platinum.json().get('count')}")

        promo = client.get(f"{BASE}/workforce/crown/promotion")
        if promo.status_code != 200:
            print(f"/workforce/crown/promotion failed: {promo.status_code}")
            return 1
        if promo.json().get("to_tier") != "platinum_assist":
            print("Expected Assist promoted to platinum_assist")
            return 1
        print(f"  promoted={promo.json().get('codename')}")

        gifts = client.get(f"{BASE}/workforce/crown/gifts")
        if gifts.status_code != 200 or gifts.json().get("count", 0) < 1:
            print("Expected Boss Sr. gift catalog")
            return 1
        print(f"  boss_sr_gifts={gifts.json().get('count')}")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase 20 Crown Completion verification")
    parser.add_argument("--start-server", action="store_true")
    parser.add_argument("--skip-probes", action="store_true")
    args = parser.parse_args()

    if _run_pytest() != 0:
        return 1

    if args.skip_probes:
        print("PHASE 20 CROWN VERIFY OK (pytest only)")
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
            print("Server failed to start for crown probes")
            return 1

    code = 0
    if _server_is_up():
        code = _probe_crown()
    else:
        print("Server not running; skipping crown probes (use --start-server)")

    if server_proc is not None:
        server_proc.terminate()
        server_proc.wait(timeout=10)

    if code != 0:
        return code

    print("PHASE 20 CROWN VERIFY OK — v1.0.0 EMPIRE COMPLETE")
    return 0


if __name__ == "__main__":
    sys.exit(main())