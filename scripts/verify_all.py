#!/usr/bin/env python3
"""Phase 5 verification: pytest + optional demo smoke test."""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
HEALTH_URL = "http://localhost:8000/api/v1/health"


def _run_pytest() -> int:
    print("=== Running pytest ===")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--tb=line", "tests/"],
        cwd=ROOT,
    )
    return result.returncode


def _server_is_up(timeout: float = 2.0) -> bool:
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.get(HEALTH_URL)
            return response.status_code == 200
    except httpx.HTTPError:
        return False


def _run_demo(*, start_server: bool) -> int:
    print("=== Running demo (no-signaling) ===")
    cmd = [sys.executable, str(ROOT / "scripts" / "demo.py"), "--no-signaling"]
    if start_server:
        cmd.append("--start-server")
    elif not _server_is_up():
        print("Server not running; skipping demo (use --start-server to auto-start).")
        return 0

    result = subprocess.run(cmd, cwd=ROOT)
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Run full Phase 5 verification")
    parser.add_argument(
        "--start-server",
        action="store_true",
        help="Start uvicorn for demo.py if not already running",
    )
    parser.add_argument(
        "--skip-demo",
        action="store_true",
        help="Only run pytest",
    )
    args = parser.parse_args()

    pytest_code = _run_pytest()
    if pytest_code != 0:
        print("pytest failed")
        return pytest_code

    if not args.skip_demo:
        demo_code = _run_demo(start_server=args.start_server)
        if demo_code != 0:
            print(f"demo failed with exit code {demo_code}")
            return demo_code

    print("PHASE 5 VERIFY OK")
    return 0


if __name__ == "__main__":
    started = time.perf_counter()
    code = main()
    elapsed = time.perf_counter() - started
    print(f"Completed in {elapsed:.1f}s")
    sys.exit(code)