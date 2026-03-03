#!/usr/bin/env sh
# POST /api/v1/sources — register a source. Args: source_id [label]
# Usage: CATCHER_URL=... ./scripts/tools/sources-register.sh my-source "My label"
set -e
BASE="${CATCHER_URL:-http://127.0.0.1:8000}"
BASE="${BASE%/}"
source_id="${1:?Missing source_id}"
label="${2:-}"
body="{\"source_id\":\"${source_id}\"}"
if [ -n "$label" ]; then
  body="{\"source_id\":\"${source_id}\",\"label\":\"${label}\"}"
fi
code=$(curl -sS -o /dev/null -w '%{http_code}' -X POST "${BASE}/api/v1/sources" \
  -H "Content-Type: application/json" -d "$body")
if [ "$code" != "200" ] && [ "$code" != "201" ]; then
  echo "Register source failed: HTTP $code" >&2
  exit 1
fi
echo "registered: ${source_id}"
