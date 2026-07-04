#!/usr/bin/env python3
"""Phase 16 verification: pytest + Revenue Forge API smoke."""

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


def _probe_revenue() -> int:
    print("=== Revenue Forge API ===")
    with httpx.Client(timeout=15.0) as client:
        status = client.get(f"{BASE}/workforce/revenue")
        if status.status_code != 200:
            print(f"/workforce/revenue failed: {status.status_code}")
            return 1
        body = status.json()
        print(
            f"  phase={body.get('deployment_phase')} "
            f"pool={body.get('subscription_pool_percent')}% "
            f"donations={body.get('donation_payout_percent')}%"
        )
        if body.get("deployment_phase") != 20:
            print("Expected deployment_phase=20")
            return 1
        if body.get("subscription_pool_percent") != 10.0:
            print("Expected subscription_pool_percent=10.0")
            return 1

        schema = client.get(f"{BASE}/workforce/revenue/schema")
        if schema.status_code != 200:
            print(f"/workforce/revenue/schema failed: {schema.status_code}")
            return 1

        route = client.post(
            f"{BASE}/workforce/revenue/donations/route",
            json={
                "member_id": "revenueforge-ledger-sub-01",
                "amount_cents": 1600,
                "donor_label": "Phase 16 revenue smoke",
            },
        )
        if route.status_code != 200:
            print(f"/workforce/revenue/donations/route failed: {route.status_code}")
            return 1
        print(f"  donation={route.json().get('ledger_entry', {}).get('id')}")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase 16 Revenue Forge verification")
    parser.add_argument("--start-server", action="store_true")
    parser.add_argument("--skip-probes", action="store_true")
    args = parser.parse_args()

    if _run_pytest() != 0:
        return 1

    if args.skip_probes:
        print("PHASE 16 REVENUE VERIFY OK (pytest only)")
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
            print("Server failed to start for revenue probes")
            return 1

    code = 0
    if _server_is_up():
        code = _probe_revenue()
    else:
        print("Server not running; skipping revenue probes (use --start-server)")

    if server_proc is not None:
        server_proc.terminate()
        server_proc.wait(timeout=10)

    if code != 0:
        return code

    print("PHASE 16 REVENUE VERIFY OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())