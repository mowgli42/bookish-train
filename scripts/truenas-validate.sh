#!/usr/bin/env sh
# Validate TrueNAS compose config and catcher health after deploy.
set -e

ROOT="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

ENV_FILE="${TRUENAS_ENV_FILE:-.env.truenas}"
COMPOSE_FILES="-f docker-compose.truenas.yml"

echo "==> compose config"
./scripts/container-compose.sh $COMPOSE_FILES --env-file "$ENV_FILE" config >/dev/null

CATCHER_PORT="${CATCHER_PORT:-8000}"
if [ -f "$ENV_FILE" ]; then
  # shellcheck disable=SC1090
  . "$ENV_FILE"
fi
CATCHER_PORT="${CATCHER_PORT:-8000}"
CATCHER_URL="${CATCHER_URL:-http://127.0.0.1:${CATCHER_PORT}}"

echo "==> health check $CATCHER_URL/health"
python3 - <<PY
import json
import sys
import urllib.request

url = "${CATCHER_URL}/health"
try:
    with urllib.request.urlopen(url, timeout=10) as resp:
        payload = json.loads(resp.read().decode())
except Exception as exc:
    print(f"health check failed: {exc}", file=sys.stderr)
    sys.exit(1)
if payload.get("status") != "ok":
    print(payload, file=sys.stderr)
    sys.exit(1)
print(json.dumps(payload, indent=2))
PY

echo "==> ingest smoke"
python3 - <<PY
import json
import urllib.request

base = "${CATCHER_URL}"
body = json.dumps({
    "source_id": "truenas-validate",
    "path": "truenas/smoke/sample.txt",
    "checksum": "abc",
    "size_bytes": 3,
}).encode()
req = urllib.request.Request(
    f"{base}/api/v1/ingest",
    data=body,
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(req, timeout=10) as resp:
    print(resp.read().decode())
PY

echo "OK: TrueNAS stack validation passed"
