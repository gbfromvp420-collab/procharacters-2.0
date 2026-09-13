#!/usr/bin/env python3
"""Phase 12 verification: pytest + provider forge API + mock and local HTTP smoke."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE = "http://127.0.0.1:8000/api/v1"

sys.path.insert(0, str(ROOT))

from app.services.providers.contract_backend import (  # noqa: E402
    pick_free_port,
    start_contract_backend,
)


def _run_pytest() -> int:
    print("=== Running pytest ===")
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--tb=line", "tests/"],
        cwd=ROOT,
    ).returncode


def _server_is_up(base: str, timeout: float = 2.0) -> bool:
    try:
        with httpx.Client(timeout=timeout) as client:
            return client.get(f"{base}/health/live").status_code == 200
    except httpx.HTTPError:
        return False


def _probe_forge(base: str, *, expect_http: bool = False) -> int:
    label = "HTTP" if expect_http else "mock"
    print(f"=== Provider forge API ({label}) ===")
    with httpx.Client(timeout=30.0) as client:
        forge = client.get(f"{base}/providers/forge")
        if forge.status_code != 200:
            print(f"/providers/forge failed: {forge.status_code}")
            return 1
        body = forge.json()
        print(f"  forge_ok={body.get('forge_ok')} live_smoke={body.get('live_smoke')}")
        print(
            f"  modes llm={body.get('llm', {}).get('mode')} "
            f"tts={body.get('tts', {}).get('mode')} "
            f"video={body.get('video', {}).get('mode')}"
        )
        if expect_http:
            if body.get("llm", {}).get("mode") != "openai_compatible":
                print("Expected llm mode=openai_compatible for HTTP path")
                return 1
            if body.get("tts", {}).get("mode") != "http":
                print("Expected tts mode=http for HTTP path")
                return 1
            if body.get("video", {}).get("mode") != "http":
                print("Expected video mode=http for HTTP path")
                return 1

        smoke = client.post(f"{base}/providers/forge/smoke")
        if smoke.status_code != 200:
            print(f"/providers/forge/smoke failed: {smoke.status_code}")
            return 1
        smoke_body = smoke.json()
        print(f"  smoke forge_ok={smoke_body.get('forge_ok')}")
        if not smoke_body.get("forge_ok"):
            print(smoke_body)
            return 1

    if not expect_http:
        print("=== Mock provider contract script ===")
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "verify_providers.py"), "--all"],
            cwd=ROOT,
        )
        return result.returncode
    return 0


def _start_uvicorn(env: dict[str, str], port: int) -> subprocess.Popen:
    merged = os.environ.copy()
    merged.update(env)
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=merged,
    )


def _wait_for_server(base: str, proc: subprocess.Popen) -> bool:
    for _ in range(50):
        if _server_is_up(base):
            return True
        if proc.poll() is not None:
            return False
        time.sleep(0.2)
    return False


def _probe_http_path() -> int:
    print("=== Local HTTP contract backend ===")
    backend = start_contract_backend()
    app_port = pick_free_port()
    app_base = f"http://127.0.0.1:{app_port}/api/v1"
    wiring_file = tempfile.NamedTemporaryFile(
        prefix="pc-wiring-",
        suffix=".json",
        delete=False,
        mode="w",
        encoding="utf-8",
    )
    wiring_file.write('{"enabled": false}\n')
    wiring_file.close()
    wiring_path = wiring_file.name
    env = backend.http_env()
    env["HOST"] = "127.0.0.1"
    env["PORT"] = str(app_port)
    env["RATE_LIMIT_ENABLED"] = "false"
    env["RUNPOD_WIRING_PATH"] = wiring_path
    server_proc = _start_uvicorn(env, app_port)
    try:
        if not _wait_for_server(app_base, server_proc):
            print("HTTP-mode app failed to start against contract backend")
            return 1

        code = _probe_forge(app_base, expect_http=True)
        if code != 0:
            return code

        print("=== HTTP provider contract script ===")
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "verify_providers.py"), "--all"],
            cwd=ROOT,
            env={**os.environ, **env},
        )
        if result.returncode != 0:
            return result.returncode

        print("=== Innovation · Wire localhost ===")
        with httpx.Client(timeout=20.0) as client:
            wire = client.post(
                f"{app_base}/workforce/innovation/wire",
                json={
                    "llm_base_url": backend.llm_base_url,
                    "tts_base_url": backend.tts_base_url,
                    "video_base_url": backend.video_base_url,
                    "enabled": True,
                },
            )
            if wire.status_code != 200 or not wire.json().get("wired"):
                print(f"innovation/wire failed: {wire.status_code} {wire.text}")
                return 1
            print(f"  wired={wire.json().get('wired')} activated={wire.json().get('pipelines_activated')}")

        print("LOCAL HTTP CONTRACT PATH OK")
        return 0
    finally:
        server_proc.terminate()
        try:
            server_proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server_proc.kill()
        backend.stop()
        try:
            os.unlink(wiring_path)
        except OSError:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase 12 Real Provider Forge verification")
    parser.add_argument("--start-server", action="store_true")
    parser.add_argument("--skip-probes", action="store_true")
    parser.add_argument(
        "--http",
        action="store_true",
        help="Also start the local contract backend and prove mock→http",
    )
    parser.add_argument(
        "--http-only",
        action="store_true",
        help="Skip mock live probes; pytest + local HTTP contract path only",
    )
    args = parser.parse_args()

    if _run_pytest() != 0:
        return 1

    if args.skip_probes:
        print("PHASE 12 FORGE VERIFY OK (pytest only)")
        return 0

    run_mock = not args.http_only
    run_http = args.http or args.http_only

    if run_mock:
        server_proc: subprocess.Popen | None = None
        if args.start_server and not _server_is_up(DEFAULT_BASE):
            server_proc = _start_uvicorn({}, 8000)
            if not _wait_for_server(DEFAULT_BASE, server_proc):
                server_proc.terminate()
                print("Server failed to start for forge probes")
                return 1

        code = 0
        if _server_is_up(DEFAULT_BASE):
            code = _probe_forge(DEFAULT_BASE, expect_http=False)
        else:
            print("Server not running; skipping mock forge probes (use --start-server)")

        if server_proc is not None:
            server_proc.terminate()
            server_proc.wait(timeout=10)

        if code != 0:
            return code

    if run_http:
        if _probe_http_path() != 0:
            return 1

    print("PHASE 12 FORGE VERIFY OK")
    if run_http:
        print("PHASE 12 HTTP CONTRACT PATH OK — no remote RunPod claimed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
