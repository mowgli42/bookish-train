#!/usr/bin/env sh
# Run compose with Podman (preferred) or Docker. Same compose file works for both.
# Usage: ./scripts/container-compose.sh [compose args...]
# Example: ./scripts/container-compose.sh -f docker-compose.phase1-assess.yml up -d catcher dashboard
# Set CONTAINER_RUNTIME=podman or CONTAINER_RUNTIME=docker to force one; otherwise auto-detect.
set -e

if [ -n "$CONTAINER_RUNTIME" ]; then
  rt="$CONTAINER_RUNTIME"
else
  if command -v podman >/dev/null 2>&1; then
    rt=podman
  elif command -v docker >/dev/null 2>&1; then
    rt=docker
  else
    echo "Need podman or docker in PATH (or set CONTAINER_RUNTIME)." >&2
    exit 1
  fi
fi

case "$rt" in
  podman)
    # Prefer podman-compose (pip install podman-compose) so no Docker Compose needed
    if command -v podman-compose >/dev/null 2>&1; then
      exec podman-compose "$@"
    else
      # Podman 4.1+: podman compose uses external provider (docker-compose or podman-compose)
      exec podman compose "$@"
    fi
    ;;
  docker)
    exec docker compose "$@"
    ;;
  *)
    echo "CONTAINER_RUNTIME must be podman or docker." >&2
    exit 1
    ;;
esac
