#!/usr/bin/env sh
# POST /api/v1/ingest — ingest one package. Env: SOURCE_ID, PACKAGE_PATH, CHECKSUM, SIZE_BYTES, TIER_HINT (optional).
# Usage: SOURCE_ID=s1 PACKAGE_PATH=file.txt CHECKSUM=abc... SIZE_BYTES=0 ./scripts/tools/ingest-one.sh
# Or: echo '{"source_id":"s1","path":"a/b.txt","checksum":"...","size_bytes":0}' | ./scripts/tools/ingest-one.sh --stdin
set -e
BASE="${CATCHER_URL:-http://127.0.0.1:8000}"
BASE="${BASE%/}"

if [ "$1" = "--stdin" ]; then
  body=$(cat)
else
  source_id="${SOURCE_ID:?Set SOURCE_ID}"
  path="${PACKAGE_PATH:?Set PACKAGE_PATH (logical path)}"
  checksum="${CHECKSUM:-}"
  size_bytes="${SIZE_BYTES:-0}"
  tier_hint="${TIER_HINT:-}"
  body="{\"source_id\":\"${source_id}\",\"path\":\"${path}\",\"checksum\":\"${checksum}\",\"size_bytes\":${size_bytes}}"
  if [ -n "$tier_hint" ]; then
    body="{\"source_id\":\"${source_id}\",\"path\":\"${path}\",\"checksum\":\"${checksum}\",\"size_bytes\":${size_bytes},\"tier_hint\":\"${tier_hint}\"}"
  fi
fi

resp=$(curl -sS -w '\n%{http_code}' -X POST "${BASE}/api/v1/ingest" \
  -H "Content-Type: application/json" -d "$body")
code=$(echo "$resp" | tail -n1)
out=$(echo "$resp" | sed '$d')
if [ "$code" != "200" ] && [ "$code" != "201" ]; then
  echo "Ingest failed: HTTP $code" >&2
  echo "$out" >&2
  exit 1
fi
# Print job_id if present
echo "$out" | grep -o '"job_id":"[^"]*"' | head -1 || echo "$out"
