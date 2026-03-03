#!/usr/bin/env sh
# GET /api/v1/config — retention rule sets and demo_mode.
# Usage: CATCHER_URL=http://localhost:8000 ./scripts/tools/config.sh
set -e
BASE="${CATCHER_URL:-http://127.0.0.1:8000}"
BASE="${BASE%/}"
curl -sS "${BASE}/api/v1/config"
