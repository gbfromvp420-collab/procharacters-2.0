#!/usr/bin/env python3
"""Wire existing RunPod proxy URLs into data/runpod_wiring.json."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.runpod_wiring import build_wiring_report, update_wiring_urls, wiring_readiness  # noqa: E402
from app.core.config import Settings  # noqa: E402

DEFAULT_PATH = ROOT / "data" / "runpod_wiring.json"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Wire RunPod Connect proxy URLs — no new pods required if you already have them",
    )
    parser.add_argument("--path", default=str(DEFAULT_PATH), help="runpod_wiring.json path")
    parser.add_argument("--llm", help="LLM/vLLM proxy URL (ends with /v1)")
    parser.add_argument("--tts", help="TTS proxy URL")
    parser.add_argument("--video", help="Video/MuseTalk proxy URL")
    parser.add_argument("--api-key", help="Shared API key for all three (optional)")
    parser.add_argument("--enable", action="store_true", help="Force enabled:true after save")
    parser.add_argument("--status", action="store_true", help="Show readiness only")
    args = parser.parse_args()

    settings = Settings(runpod_wiring_path=args.path)

    if args.status or not any((args.llm, args.tts, args.video, args.api_key, args.enable)):
        report = build_wiring_report(settings)
        readiness = report["readiness"]
        print(json.dumps({"readiness": readiness, "message": report.get("notes", "")}, indent=2))
        if readiness.get("wired"):
            print("\nWired — run: curl -X POST http://localhost:8000/api/v1/providers/forge/smoke")
        elif readiness.get("all_ready"):
            print("\nURLs ready — run with --enable or set enabled:true in JSON")
        else:
            missing = []
            if not readiness.get("llm_ready"):
                missing.append("LLM (--llm)")
            if not readiness.get("tts_ready"):
                missing.append("TTS (--tts)")
            if not readiness.get("video_ready"):
                missing.append("Video (--video)")
            print(f"\nStill need: {', '.join(missing)}")
        return 0 if readiness.get("wired") or args.status else 1

    wiring = update_wiring_urls(
        path=args.path,
        llm_base_url=args.llm,
        tts_base_url=args.tts,
        video_base_url=args.video,
        api_key=args.api_key,
        enabled=True if args.enable else None,
    )
    readiness = wiring_readiness(wiring)
    print(json.dumps(readiness, indent=2))
    if readiness["wired"]:
        print("\nRunPod wired. Restart server if running, then forge smoke.")
        return 0
    if readiness["all_ready"]:
        print("\nURLs saved. Re-run with --enable to activate.")
        return 0
    print("\nPartial wire — fill remaining URLs and retry.")
    return 1


if __name__ == "__main__":
    sys.exit(main())