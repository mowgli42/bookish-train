#!/usr/bin/env sh
# GET /health — exit 0 if catcher is ok.
# Usage: CATCHER_URL=http://localhost:8000 ./scripts/tools/health.sh
set -e
BASE="${CATCHER_URL:-http://127.0.0.1:8000}"
BASE="${BASE%/}"
resp=$(curl -sS -w '\n%{http_code}' "${BASE}/health")
code=$(echo "$resp" | tail -n1)
body=$(echo "$resp" | sed '$d')
if [ "$code" != "200" ]; then
  echo "Health check failed: HTTP $code" >&2
  echo "$body" >&2
  exit 1
fi
# Optional: check status in JSON (requires grep/sed; keep minimal for portability)
if echo "$body" | grep -q '"status"[[:space:]]*:[[:space:]]*"ok"'; then
  echo "ok"
  exit 0
fi
echo "Unexpected response: $body" >&2
exit 1
