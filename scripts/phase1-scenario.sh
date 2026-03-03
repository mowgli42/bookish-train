#!/usr/bin/env sh
# Phase 1 workflow scenario: validate catcher API and tooling end-to-end.
# Run with CATCHER_URL set (default http://127.0.0.1:8000). In Docker use CATCHER_URL=http://catcher:8000.
# Exit 0 only if all steps pass.
set -e

# Resolve script dir (POSIX; works with sh and bash)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
export CATCHER_URL="${CATCHER_URL:-http://127.0.0.1:8000}"
SOURCE_ID="phase1-scenario-source"

echo "=== Phase 1 scenario (CATCHER_URL=$CATCHER_URL) ==="

# 1. Health
echo "[1/7] Health check..."
"$SCRIPT_DIR/tools/health.sh" || { echo "FAIL: health"; exit 1; }

# 2. Reset state
echo "[2/7] Demo reset..."
"$SCRIPT_DIR/tools/demo-reset.sh" || { echo "FAIL: demo-reset"; exit 1; }

# 3. Register source and seed from MANIFEST
echo "[3/7] Register source and seed..."
"$SCRIPT_DIR/tools/sources-register.sh" "$SOURCE_ID" "Phase 1 scenario" || { echo "FAIL: register source"; exit 1; }
if [ -f "$REPO_ROOT/scripts/seed-demo-data.py" ]; then
  python3 "$REPO_ROOT/scripts/seed-demo-data.py" --source "$SOURCE_ID" --url "$CATCHER_URL" || { echo "FAIL: seed"; exit 1; }
else
  echo "WARN: seed-demo-data.py not found; skipping seed (ingest at least one manually for full check)"
  # Ingest one minimal package so later checks have data
  CHECKSUM="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
  SOURCE_ID="$SOURCE_ID" PACKAGE_PATH="scenario-placeholder.txt" CHECKSUM="$CHECKSUM" SIZE_BYTES=0 \
    "$SCRIPT_DIR/tools/ingest-one.sh" || true
fi

# 4. Packages
echo "[4/7] Packages..."
packages="$("$SCRIPT_DIR/tools/packages-list.sh")"
if ! echo "$packages" | grep -qE '"job_id"|"package_id"'; then
  echo "FAIL: no packages in response"; echo "$packages" | head -3; exit 1
fi

# 5. Buckets
echo "[5/7] Buckets..."
buckets="$("$SCRIPT_DIR/tools/buckets.sh")"
if ! echo "$buckets" | grep -q '"buckets"'; then
  echo "FAIL: no buckets in response"; echo "$buckets" | head -3; exit 1
fi

# 6. Sources
echo "[6/7] Sources..."
sources="$("$SCRIPT_DIR/tools/sources-list.sh")"
if ! echo "$sources" | grep -q "$SOURCE_ID"; then
  echo "FAIL: source $SOURCE_ID not in list"; echo "$sources" | head -3; exit 1
fi

# 7. Config and projections
echo "[7/7] Config and projections..."
config="$("$SCRIPT_DIR/tools/config.sh")"
echo "$config" | grep -qE '"rule_sets"|"retention"' || { echo "FAIL: config missing rule_sets/retention"; exit 1; }
proj="$("$SCRIPT_DIR/tools/projections.sh" 5)"
echo "$proj" | grep -q '"transitions"' || { echo "FAIL: projections missing transitions"; exit 1; }

echo ""
echo "=== Phase 1 scenario OK ==="
