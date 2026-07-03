#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate 2>/dev/null || true

# Usage:
#   ./scripts/run.sh                 # dev with --reload
#   PORT=9000 ./scripts/run.sh       # custom port
#   RELOAD=0 ./scripts/run.sh        # no-reload (good for demo / prod-like)
#   ./scripts/run.sh --demo          # start server (no-reload) then run the verification demo.py
# After start, use: python scripts/demo.py   (or with --start-server)

RELOAD_FLAG="--reload"
if [[ "${RELOAD:-1}" == "0" || "${1:-}" == "--no-reload" ]]; then
  RELOAD_FLAG="--no-reload"
fi

echo "Starting ProCharacters Cloud (uvicorn ${RELOAD_FLAG})..."

if [[ "${1:-}" == "--demo" ]]; then
  # Start non-reloading server in bg, run demo, cleanup
  uvicorn app.main:app ${RELOAD_FLAG} --host 0.0.0.0 --port "${PORT:-8000}" &
  UV_PID=$!
  trap 'echo "[run.sh] killing uvicorn $UV_PID"; kill $UV_PID 2>/dev/null || true' EXIT
  echo "Waiting for server..."
  for i in {1..40}; do
    if curl -sf "http://localhost:${PORT:-8000}/api/v1/health" >/dev/null 2>&1; then break; fi
    sleep 0.25
  done
  python scripts/demo.py --no-signaling || true
  exit 0
fi

exec uvicorn app.main:app ${RELOAD_FLAG} --host 0.0.0.0 --port "${PORT:-8000}"
