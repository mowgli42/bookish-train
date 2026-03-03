#!/usr/bin/env sh
# GET /api/v1/packages — list packages (optional ?status= &c).
# Usage: CATCHER_URL=http://localhost:8000 ./scripts/tools/packages-list.sh [query]
# Example: ./scripts/tools/packages-list.sh '?source_id=demo-seed'
set -e
BASE="${CATCHER_URL:-http://127.0.0.1:8000}"
BASE="${BASE%/}"
query="${1:-}"
curl -sS "${BASE}/api/v1/packages${query}"
