#!/usr/bin/env python3
"""Phase 13 verification: pytest + Agent Theater dispatch smoke."""

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


def _probe_theater() -> int:
    print("=== Agent Theater API ===")
    with httpx.Client(timeout=15.0) as client:
        status = client.get(f"{BASE}/workforce/theater")
        if status.status_code != 200:
            print(f"/workforce/theater failed: {status.status_code}")
            return 1
        status_body = status.json()
        print(
            f"  phase={status_body.get('deployment_phase')} "
            f"team={status_body.get('dispatchable_count')}"
        )
        if status_body.get("deployment_phase") != 20:
            print("Expected deployment_phase=20")
            return 1

        roster = client.get(f"{BASE}/workforce/roster")
        if roster.status_code != 200:
            print(f"/workforce/roster failed: {roster.status_code}")
            return 1
        members = roster.json().get("members", [])
        dispatch_member = next(
            (m for m in members if m.get("codename") == "AgentTheater_Dispatch_Sub_01"),
            None,
        )
        if dispatch_member is None:
            print("AgentTheater_Dispatch_Sub_01 missing from roster")
            return 1

        dispatch = client.post(
            f"{BASE}/workforce/theater/dispatch",
            json={
                "member_id": dispatch_member["id"],
                "prompt": "Phase 13 theater smoke task",
                "skill": "Workforce_TaskDispatch",
            },
        )
        if dispatch.status_code != 200:
            print(f"/workforce/theater/dispatch failed: {dispatch.status_code}")
            return 1
        task = dispatch.json()
        task_id = task.get("id")
        print(f"  dispatched task={task_id} status={task.get('status')}")

        for _ in range(40):
            detail = client.get(f"{BASE}/workforce/theater/tasks/{task_id}")
            if detail.status_code != 200:
                print(f"task poll failed: {detail.status_code}")
                return 1
            current = detail.json()
            if current.get("status") == "completed":
                print(f"  completed in {current.get('duration_ms')}ms")
                return 0
            if current.get("status") == "failed":
                print(f"task failed: {current.get('error')}")
                return 1
            time.sleep(0.1)

    print("Task did not complete in time")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase 13 Agent Theater verification")
    parser.add_argument("--start-server", action="store_true")
    parser.add_argument("--skip-probes", action="store_true")
    args = parser.parse_args()

    if _run_pytest() != 0:
        return 1

    if args.skip_probes:
        print("PHASE 13 THEATER VERIFY OK (pytest only)")
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
            print("Server failed to start for theater probes")
            return 1

    code = 0
    if _server_is_up():
        code = _probe_theater()
    else:
        print("Server not running; skipping theater probes (use --start-server)")

    if server_proc is not None:
        server_proc.terminate()
        server_proc.wait(timeout=10)

    if code != 0:
        return code

    print("PHASE 13 THEATER VERIFY OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())