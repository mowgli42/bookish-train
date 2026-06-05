#!/usr/bin/env bash
# Quick verification that the system works.
# Prerequisites: backend deps installed (pip install -r backend/requirements.txt)
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

echo "=== Backend checksum validation ==="
cd backend
PY="${REPO_ROOT}/backend/.venv/bin/python"
if [ ! -x "$PY" ]; then
  PY=python3
fi
"$PY" -c "
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
echo "=== Dispatcher journal, resume, and config snapshots ==="
python3 - <<'PY'
from backend import main

main.JOBS.clear()
main.SOURCES.clear()
main.JOURNAL.clear()
main.CONFIG_SNAPSHOTS.clear()
main.DELETED_COUNT = 0
main._JOB_ID = 0
main._JOURNAL_ID = 0
main._SNAPSHOT_ID = 0

source = main.SourceBody(source_id="verify-engine", label="Verify Engine")
main.register_source(source)
job_id = main.ingest(main.IngestBody(
    source_id="verify-engine",
    path="s3/Pictures/family.jpg",
    checksum="a" * 64,
    size_bytes=12,
    package_type="user_data",
))["job_id"]
main.patch_package(job_id, main.PackagePatch(status="failed", progress_percent=55, last_error="network interruption"))

resume = main.resume_switch_list("verify-engine")
assert resume["count"] == 1
assert resume["switch_list"][0]["package_id"] == job_id
assert resume["switch_list"][0]["station_id"] == "s3"
assert resume["switch_list"][0]["last_error"] == "network interruption"

events = [e["event_type"] for e in main.list_journal(source_id="verify-engine")]
for expected in ("client_registered", "manifest_created", "transfer_failed", "resume_requested"):
    assert expected in events, expected

snapshots = main.list_config_snapshots()
assert snapshots and snapshots[0]["snapshot_id"]
manual = main.create_config_snapshot()
assert main.export_config()["hash"]
assert main.restore_config_snapshot(manual["snapshot_id"])["restored"] == manual["snapshot_id"]
print("OK: dispatcher journal/resume/snapshots")
PY

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
echo "=== Observability demo and sample logs ==="
python3 scripts/demo-observability.py --write-samples --no-failure >/dev/null
test -f docs/samples/agent-logs-sample.jsonl
test -f docs/samples/agent-ebk-sample.txt
python3 - <<'PY'
import json
from pathlib import Path

jsonl = Path("docs/samples/agent-logs-sample.jsonl").read_text(encoding="utf-8").strip().splitlines()
assert len(jsonl) >= 3
failure = [json.loads(line) for line in jsonl if "transfer_failed" in line]
# full demo with failure is documented in samples; regenerate with default (includes failure)
from subprocess import run
run(["python3", "scripts/demo-observability.py", "--write-samples"], check=True, capture_output=True)
jsonl = Path("docs/samples/agent-logs-sample.jsonl").read_text(encoding="utf-8").strip().splitlines()
records = [json.loads(line) for line in jsonl]
failed = [r for r in records if r.get("event_type") == "transfer_failed"]
assert failed and failed[0].get("error_source") == "home-backup-chain-demo"
assert failed[0].get("operation") == "copy_hop"
ebk = Path("docs/samples/agent-ebk-sample.txt").read_text(encoding="utf-8")
assert "EBK" in ebk
assert "error_source=home-backup-chain-demo" in ebk or "command=error" in ebk
print("OK: sample logs include error_source and EBK lines")
PY

echo ""
echo "=== Silver Fiesta transfer protocol validation ==="
SF_PY="${REPO_ROOT}/backend/.venv/bin/python"
if [ ! -x "$SF_PY" ]; then
  SF_PY=python3
fi
EBK_AI_STATUS=0 "$SF_PY" scripts/silver-fiesta.py --root /tmp/edge-backup-protocol-verify --protocol local_chunked --format json >/tmp/edge-backup-protocol-verify-summary.json
python3 - <<'PY'
import json
from pathlib import Path

summary = json.loads(Path("/tmp/edge-backup-protocol-verify-summary.json").read_text(encoding="utf-8"))
assert summary["protocols"][0]["protocol"] == "local_chunked"
assert summary["protocols"][0]["ok"] is True
log_path = Path(summary["transfer_log"])
records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
assert any(r["action"] == "transfer_completed" and r.get("throughput_mib_s") for r in records)
print("OK: silver-fiesta local_chunked probe with performance annotations")
PY

echo ""
echo "=== Silver Fiesta sample logs ==="
"$SF_PY" scripts/write-silver-fiesta-samples.py --check

echo ""
echo "=== Observability and AI agent CLI ==="
"$SF_PY" -m pytest tests/unit/test_edge_observability.py tests/unit/test_backup_agent.py tests/unit/test_silver_fiesta.py tests/unit/test_silver_fiesta_samples.py -q
python3 scripts/backup-agent.py commands --format ai | head -n 3
echo "OK: observability and backup-agent"

echo ""
echo "=== Compose config (optional) ==="
if command -v podman &>/dev/null; then
  ./scripts/container-compose.sh -f docker-compose.phase1-assess.yml config -q 2>/dev/null && echo "OK: compose valid (podman)" || true
elif command -v docker &>/dev/null; then
  docker compose -f docker-compose.phase1-assess.yml config -q 2>/dev/null && echo "OK: compose valid (docker)" || true
else
  echo "Skip: podman/docker not installed"
fi
