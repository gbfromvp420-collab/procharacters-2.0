#!/usr/bin/env python3
"""Phase 11 verification: pytest + liveness/readiness probe smoke."""

from __future__ import annotations

import argparse
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://localhost:8000/api/v1"


def _run_pytest() -> int:
    print("=== Running pytest ===")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--tb=line", "tests/"],
        cwd=ROOT,
    )
    return result.returncode


def _port_open(port: int = 8000) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex(("127.0.0.1", port)) == 0


def _server_is_up(timeout: float = 2.0) -> bool:
    try:
        with httpx.Client(timeout=timeout) as client:
            return client.get(f"{BASE}/health/live").status_code == 200
    except httpx.HTTPError:
        return False


def _probe_endpoints() -> int:
    print("=== Probing liveness + readiness ===")
    with httpx.Client(timeout=5.0) as client:
        live = client.get(f"{BASE}/health/live")
        if live.status_code != 200:
            print(f"/health/live failed: {live.status_code}")
            return 1
        live_body = live.json()
        print(f"  live: v{live_body.get('version')} phase={live_body.get('deployment_phase')}")

        ready = client.get(f"{BASE}/health/ready")
        if ready.status_code != 200:
            print(f"/health/ready failed: {ready.status_code} {ready.text}")
            return 1
        ready_body = ready.json()
        print(f"  ready: {ready_body.get('status')} checks={list(ready_body.get('checks', {}).keys())}")

        health = client.get(f"{BASE}/health")
        if health.status_code != 200:
            print(f"/health failed: {health.status_code}")
            return 1
        print(f"  health: {health.json().get('status')}")

    return 0


def _run_demo(*, start_server: bool) -> int:
    print("=== Running demo (no-signaling) ===")
    cmd = [sys.executable, str(ROOT / "scripts" / "demo.py"), "--no-signaling"]
    if start_server:
        cmd.append("--start-server")
    elif not _server_is_up():
        print("Server not running; skipping demo (use --start-server to auto-start).")
        return 0

    return subprocess.run(cmd, cwd=ROOT).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase 11 Empire Launch verification")
    parser.add_argument(
        "--start-server",
        action="store_true",
        help="Start uvicorn for probe/demo steps if not already running",
    )
    parser.add_argument("--skip-demo", action="store_true", help="Only run pytest + probes")
    parser.add_argument(
        "--skip-probes",
        action="store_true",
        help="Only run pytest (and optional demo)",
    )
    args = parser.parse_args()

    pytest_code = _run_pytest()
    if pytest_code != 0:
        print("pytest failed")
        return pytest_code

    server_proc: subprocess.Popen | None = None
    if not args.skip_probes:
        if args.start_server and not _server_is_up():
            server_proc = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "app.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "8000",
                ],
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
                if _port_open():
                    print(
                        "Port 8000 is in use but /health/live is unavailable — "
                        "restart uvicorn to pick up Phase 11 probes."
                    )
                else:
                    print("Server failed to start for probe step")
                return 1

        if _server_is_up():
            probe_code = _probe_endpoints()
            if probe_code != 0:
                return probe_code
        else:
            print("Server not running; skipping live/ready probes (use --start-server).")

    if server_proc is not None:
        server_proc.terminate()
        server_proc.wait(timeout=10)

    if not args.skip_demo:
        demo_code = _run_demo(start_server=args.start_server)
        if demo_code != 0:
            print(f"demo failed with exit code {demo_code}")
            return demo_code

    print("PHASE 11 EMPIRE VERIFY OK")
    return 0


if __name__ == "__main__":
    started = time.perf_counter()
    code = main()
    elapsed = time.perf_counter() - started
    print(f"Completed in {elapsed:.1f}s")
    sys.exit(code)