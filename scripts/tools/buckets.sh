#!/usr/bin/env sh
# GET /api/v1/buckets — bucket summary (counts, bytes per tier).
# Usage: CATCHER_URL=http://localhost:8000 ./scripts/tools/buckets.sh
set -e
BASE="${CATCHER_URL:-http://127.0.0.1:8000}"
BASE="${BASE%/}"
curl -sS "${BASE}/api/v1/buckets"
