#!/usr/bin/env sh
# Run the catcher backend with a venv so dependencies (fastapi, uvicorn) are available.
# Usage: ./scripts/run-backend.sh   or   DEMO_MODE=1 ./scripts/run-backend.sh
# If port 8000 is in use: PORT=8001 ./scripts/run-backend.sh  (then CATCHER_URL=http://127.0.0.1:8001 for run-demo; frontend may need VITE_PROXY_API)
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV="$REPO_ROOT/backend/.venv"
BACKEND="$REPO_ROOT/backend"
PORT="${PORT:-8000}"

if [ ! -d "$VENV" ]; then
  echo "Creating backend venv at $VENV..."
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install -q -r "$BACKEND/requirements.txt"
fi

cd "$BACKEND"
exec "$VENV/bin/python" -m uvicorn main:app --host 127.0.0.1 --port "$PORT"
