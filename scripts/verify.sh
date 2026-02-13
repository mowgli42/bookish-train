#!/usr/bin/env bash
# Quick verification that the system works.
# Prerequisites: backend deps installed (pip install -r backend/requirements.txt)
set -e
cd "$(dirname "$0")/.."

echo "=== Backend checksum validation ==="
cd backend
python -c "
from main import IngestBody
try:
    IngestBody(source_id='x', path='y', size_bytes=1, checksum=None)
    raise SystemExit(1)
except ValueError:
    print('OK: rejects size_bytes>0 without checksum')
m = IngestBody(source_id='x', path='y', size_bytes=1, checksum='abc')
print('OK: accepts valid ingest')
"
cd ..

echo ""
echo "=== Docker build (optional) ==="
if command -v docker &>/dev/null; then
  docker compose config -q && echo "OK: docker-compose valid" || true
else
  echo "Skip: docker not installed"
fi
