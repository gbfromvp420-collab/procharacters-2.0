#!/usr/bin/env python3
"""Run the local HTTP contract backend (LLM + TTS + Video shapes)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.providers.contract_backend import main  # noqa: E402

if __name__ == "__main__":
    main()
