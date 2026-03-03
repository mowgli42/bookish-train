#!/usr/bin/env sh
# POST /api/v1/demo/reset — clear jobs, sources, deleted count.
# Usage: CATCHER_URL=http://localhost:8000 ./scripts/tools/demo-reset.sh
set -e
BASE="${CATCHER_URL:-http://127.0.0.1:8000}"
BASE="${BASE%/}"
code=$(curl -sS -o /dev/null -w '%{http_code}' -X POST "${BASE}/api/v1/demo/reset")
if [ "$code" != "200" ]; then
  echo "Demo reset failed: HTTP $code" >&2
  exit 1
fi
echo "reset ok"
