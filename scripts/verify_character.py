#!/usr/bin/env python3
"""Phase 17 verification: pytest + Character Forge API smoke."""

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


def _probe_character() -> int:
    print("=== Character Forge API ===")
    with httpx.Client(timeout=15.0) as client:
        status = client.get(f"{BASE}/workforce/characters")
        if status.status_code != 200:
            print(f"/workforce/characters failed: {status.status_code}")
            return 1
        body = status.json()
        print(
            f"  phase={body.get('deployment_phase')} "
            f"characters={body.get('characters_total')} "
            f"contact={body.get('contact_email')}"
        )
        if body.get("deployment_phase") != 20:
            print("Expected deployment_phase=20")
            return 1
        if body.get("contact_email") != "gary@procharacters.cloud":
            print("Expected gary@procharacters.cloud contact")
            return 1

        onboard = client.post(
            f"{BASE}/workforce/characters/onboard",
            json={
                "member_id": "characterforge-nsm-sub-01",
                "display_name": "Phase 17 NSM smoke",
                "avatar_id": "professional",
            },
        )
        if onboard.status_code != 200:
            print(f"/workforce/characters/onboard failed: {onboard.status_code}")
            return 1
        character_id = onboard.json().get("id")
        print(f"  character={character_id}")

        residual = client.post(
            f"{BASE}/workforce/characters/residuals",
            json={
                "character_id": character_id,
                "asset_type": "distribution",
                "amount_cents": 5000,
                "description": "Phase 17 character smoke — distribution bonus",
            },
        )
        if residual.status_code != 200:
            print(f"/workforce/characters/residuals failed: {residual.status_code}")
            return 1
        print(f"  residual={residual.json().get('id')}")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase 17 Character Forge verification")
    parser.add_argument("--start-server", action="store_true")
    parser.add_argument("--skip-probes", action="store_true")
    args = parser.parse_args()

    if _run_pytest() != 0:
        return 1

    if args.skip_probes:
        print("PHASE 17 CHARACTER VERIFY OK (pytest only)")
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
            print("Server failed to start for character probes")
            return 1

    code = 0
    if _server_is_up():
        code = _probe_character()
    else:
        print("Server not running; skipping character probes (use --start-server)")

    if server_proc is not None:
        server_proc.terminate()
        server_proc.wait(timeout=10)

    if code != 0:
        return code

    print("PHASE 17 CHARACTER VERIFY OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())