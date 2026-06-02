#!/usr/bin/env sh
# Start containers with latest frontend/backend. Forces rebuild of dashboard so you get the latest UI.
# Usage: ./scripts/up.sh [--no-fresh]
#   ./scripts/up.sh         # build --no-cache dashboard, then up -d (latest UI)
#   ./scripts/up.sh --no-fresh   # skip --no-cache (faster, may use cached build)
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE="$SCRIPT_DIR/container-compose.sh"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"

FRESH=true
[ "$1" = "--no-fresh" ] && FRESH=false

cd "$REPO_ROOT"

"$SCRIPT_DIR/sync-test-data.sh" 2>/dev/null || true

if [ "$FRESH" = true ]; then
  echo "Building dashboard (no cache) for latest UI..."
  $COMPOSE -f "$COMPOSE_FILE" build --no-cache dashboard
fi

echo "Starting containers..."
$COMPOSE -f "$COMPOSE_FILE" up -d --build

echo ""
echo "Dashboard: http://127.0.0.1:5173  |  Catcher: http://127.0.0.1:8000"
