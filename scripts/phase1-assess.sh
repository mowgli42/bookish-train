#!/usr/bin/env sh
# Phase 1 assessment: start stack with Podman (or Docker), then run scenario in tools container.
# Usage: ./scripts/phase1-assess.sh [--no-run]   (default: up -d, then run phase1-tools; --no-run: only start stack)
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="$REPO_ROOT/docker-compose.phase1-assess.yml"
CATCHER_URL="${CATCHER_URL:-http://127.0.0.1:8000}"

only_up=false
for a in "$@"; do
  case "$a" in
    --no-run) only_up=true ;;
  esac
done

cd "$REPO_ROOT"

# Prefer Podman; use container-compose.sh so we get podman/docker automatically
COMPOSE_CMD="$SCRIPT_DIR/container-compose.sh -f $COMPOSE_FILE"

echo "=== Phase 1 assessment (using $COMPOSE_CMD) ==="
echo ""

echo "[1/3] Building and starting catcher + dashboard..."
$COMPOSE_CMD up -d --build catcher dashboard

echo ""
echo "[2/3] Waiting for catcher health..."
# Poll /health; Podman/Docker network may need a few seconds for DNS
i=0
while [ $i -lt 30 ]; do
  if curl -sS --connect-timeout 2 "$CATCHER_URL/health" | grep -q '"status"[[:space:]]*:[[:space:]]*"ok"'; then
    echo "Catcher is up."
    break
  fi
  i=$((i + 1))
  sleep 1
done
if [ $i -eq 30 ]; then
  echo "WARN: Catcher health check timed out; continuing anyway."
fi

if [ "$only_up" = true ]; then
  echo ""
  echo "Stack is up. Run scenario with: $COMPOSE_CMD run --rm phase1-tools"
  exit 0
fi

echo ""
echo "[3/3] Running scenario in phase1-tools container..."
$COMPOSE_CMD run --rm phase1-tools

echo ""
echo "=== Phase 1 assessment done ==="
