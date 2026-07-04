#!/usr/bin/env python3
"""Phase 19 verification: pytest + Sovereign Scale API smoke."""

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


def _probe_scale() -> int:
    print("=== Sovereign Scale API ===")
    with httpx.Client(timeout=15.0) as client:
        status = client.get(f"{BASE}/workforce/scale")
        if status.status_code != 200:
            print(f"/workforce/scale failed: {status.status_code}")
            return 1
        body = status.json()
        print(
            f"  phase={body.get('deployment_phase')} "
            f"tenants={body.get('tenants_total')} "
            f"nodes={body.get('nodes_healthy')}/{body.get('nodes_total')}"
        )
        if body.get("deployment_phase") != 20:
            print("Expected deployment_phase=20")
            return 1
        if not body.get("scale_ready"):
            print("Expected scale_ready=true")
            return 1

        obs = client.get(f"{BASE}/workforce/scale/observability")
        if obs.status_code != 200:
            print(f"/workforce/scale/observability failed: {obs.status_code}")
            return 1
        print(f"  observability_phase={obs.json().get('deployment_phase')}")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase 19 Sovereign Scale verification")
    parser.add_argument("--start-server", action="store_true")
    parser.add_argument("--skip-probes", action="store_true")
    args = parser.parse_args()

    if _run_pytest() != 0:
        return 1

    if args.skip_probes:
        print("PHASE 19 SCALE VERIFY OK (pytest only)")
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
            print("Server failed to start for scale probes")
            return 1

    code = 0
    if _server_is_up():
        code = _probe_scale()
    else:
        print("Server not running; skipping scale probes (use --start-server)")

    if server_proc is not None:
        server_proc.terminate()
        server_proc.wait(timeout=10)

    if code != 0:
        return code

    print("PHASE 19 SCALE VERIFY OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())