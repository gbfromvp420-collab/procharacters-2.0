#!/usr/bin/env python3
"""Phase 12 verification: pytest + provider forge API + contract smoke (mock)."""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
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


def _probe_forge() -> int:
    print("=== Provider forge API ===")
    with httpx.Client(timeout=15.0) as client:
        forge = client.get(f"{BASE}/providers/forge")
        if forge.status_code != 200:
            print(f"/providers/forge failed: {forge.status_code}")
            return 1
        body = forge.json()
        print(f"  forge_ok={body.get('forge_ok')} live_smoke={body.get('live_smoke')}")

        smoke = client.post(f"{BASE}/providers/forge/smoke")
        if smoke.status_code != 200:
            print(f"/providers/forge/smoke failed: {smoke.status_code}")
            return 1
        smoke_body = smoke.json()
        print(f"  smoke forge_ok={smoke_body.get('forge_ok')}")
        if not smoke_body.get("forge_ok"):
            return 1

    print("=== Mock provider contract script ===")
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "verify_providers.py"), "--all"],
        cwd=ROOT,
    )
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase 12 Real Provider Forge verification")
    parser.add_argument("--start-server", action="store_true")
    parser.add_argument("--skip-probes", action="store_true")
    args = parser.parse_args()

    if _run_pytest() != 0:
        return 1

    if args.skip_probes:
        print("PHASE 12 FORGE VERIFY OK (pytest only)")
        return 0

    server_proc: subprocess.Popen | None = None
    if args.start_server and not _server_is_up():
        server_proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(40):
            if _server_is_up():
                break
            time.sleep(0.25)
        else:
            if server_proc is not None:
                server_proc.terminate()
            print("Server failed to start for forge probes")
            return 1

    code = 0
    if _server_is_up():
        code = _probe_forge()
    else:
        print("Server not running; skipping forge probes (use --start-server)")

    if server_proc is not None:
        server_proc.terminate()
        server_proc.wait(timeout=10)

    if code != 0:
        return code

    print("PHASE 12 FORGE VERIFY OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())