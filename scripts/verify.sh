#!/usr/bin/env bash
# Quick verification that the system works.
# Prerequisites: backend deps installed (pip install -r backend/requirements.txt)
set -e
cd "$(dirname "$0")/.."

echo "=== Backend checksum validation ==="
cd backend
python3 -c "
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
echo "=== Local provider-chain demo ==="
python3 scripts/home-backup-chain-demo.py --no-catcher --root /tmp/edge-backup-home-chain-verify --pause 0
python3 - <<'PY'
from pathlib import Path

root = Path("/tmp/edge-backup-home-chain-verify")
for rel in [
    "google-drive/EdgeBackup/home-client-package.tar.gz",
    "backup-service/vault/home-client-package.tar.gz",
]:
    path = root / rel
    if path.exists():
        path.unlink()
print("OK: removed downstream copies for resend validation")
PY
python3 scripts/home-backup-chain-demo.py --no-catcher --root /tmp/edge-backup-home-chain-verify --resend-from-log --pause 0
python3 - <<'PY'
import json
from pathlib import Path

root = Path("/tmp/edge-backup-home-chain-verify")
log_path = root / "home-client" / "transfer-log.jsonl"
records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
assert any(r["action"] == "package_created" for r in records)
assert any(r["action"] == "transfer_completed" and r.get("mode") == "send" for r in records)
assert any(r["action"] == "transfer_completed" and r.get("mode") == "resend" for r in records)
for rel in [
    "local-nas/edge-backups/home-client-package.tar.gz",
    "google-drive/EdgeBackup/home-client-package.tar.gz",
    "backup-service/vault/home-client-package.tar.gz",
]:
    assert (root / rel).exists(), rel
print("OK: transfer log and resend validation passed")
PY

echo ""
echo "=== Compose config (optional) ==="
if command -v podman &>/dev/null; then
  ./scripts/container-compose.sh -f docker-compose.phase1-assess.yml config -q 2>/dev/null && echo "OK: compose valid (podman)" || true
elif command -v docker &>/dev/null; then
  docker compose -f docker-compose.phase1-assess.yml config -q 2>/dev/null && echo "OK: compose valid (docker)" || true
else
  echo "Skip: podman/docker not installed"
fi
