#!/usr/bin/env sh
# GET /api/v1/sources — list registered sources.
# Usage: CATCHER_URL=http://localhost:8000 ./scripts/tools/sources-list.sh
set -e
BASE="${CATCHER_URL:-http://127.0.0.1:8000}"
BASE="${BASE%/}"
curl -sS "${BASE}/api/v1/sources"
