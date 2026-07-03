#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate 2>/dev/null || true
echo "Starting ProCharacters Cloud (uvicorn)..."
exec uvicorn app.main:app --reload --host 0.0.0.0 --port "${PORT:-8000}"
