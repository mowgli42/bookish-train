#!/usr/bin/env sh
# Copy mock fixtures into clients/docker-client/test-data for local tools that expect that path.
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SRC="$REPO_ROOT/tests/fixtures/mock-data"
DEST="$REPO_ROOT/clients/docker-client/test-data"

if [ ! -d "$SRC" ]; then
  echo "Missing fixtures: $SRC" >&2
  exit 1
fi

mkdir -p "$DEST"
# rsync if available, else cp
if command -v rsync >/dev/null 2>&1; then
  rsync -a --delete --exclude MANIFEST.json "$SRC/" "$DEST/"
else
  rm -rf "$DEST"/*
  cp -a "$SRC/." "$DEST/"
  rm -f "$DEST/MANIFEST.json"
fi

echo "Synced test-data from tests/fixtures/mock-data → clients/docker-client/test-data"
