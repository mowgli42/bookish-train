#!/usr/bin/env sh
# Shut down Podman/Docker containers used for testing so ports (e.g. 8000, 5173) are free.
# Uses the same runtime as container-compose.sh (Podman preferred). Run from repo root.
# Usage: ./scripts/container-down.sh [--all]
#   default: down only docker-compose.phase1-assess.yml (assessment stack)
#   --all:   down both phase1-assess and docker-compose.yml (main stack)
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE="$SCRIPT_DIR/container-compose.sh"

cd "$REPO_ROOT"

_down() {
  local file="$1"
  echo "Shutting down: $file"
  $COMPOSE -f "$file" down --remove-orphans 2>/dev/null || true
}

_down "docker-compose.phase1-assess.yml"

case "${1:-}" in
  --all)
    _down "docker-compose.yml"
    ;;
  *)
    echo "Tip: use --all to also shut down docker-compose.yml (main stack)."
    ;;
esac

echo "Done. Ports 8000 and 5173 should be free."
