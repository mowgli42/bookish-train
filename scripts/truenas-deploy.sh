#!/usr/bin/env sh
# Deploy or manage the TrueNAS-oriented compose stack.
# Usage: ./scripts/truenas-deploy.sh up -d
set -e

ROOT="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

ENV_FILE="${TRUENAS_ENV_FILE:-.env.truenas}"
if [ ! -f "$ENV_FILE" ] && [ -f .env.truenas.example ]; then
  echo "Creating $ENV_FILE from .env.truenas.example"
  cp .env.truenas.example "$ENV_FILE"
fi

COMPOSE_FILES="-f docker-compose.truenas.yml"
if [ "${TRUENAS_OBSERVABILITY:-0}" = "1" ]; then
  COMPOSE_FILES="$COMPOSE_FILES --profile observability"
fi

exec ./scripts/container-compose.sh $COMPOSE_FILES --env-file "$ENV_FILE" "$@"
