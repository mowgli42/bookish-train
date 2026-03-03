#!/usr/bin/env sh
# GET /api/v1/projections?days=N — upcoming bucket transitions.
# Usage: CATCHER_URL=... ./scripts/tools/projections.sh [days]
# Default days=5.
set -e
BASE="${CATCHER_URL:-http://127.0.0.1:8000}"
BASE="${BASE%/}"
days="${1:-5}"
curl -sS "${BASE}/api/v1/projections?days=${days}"
