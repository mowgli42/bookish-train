#!/usr/bin/env bash
# Run Silver Fiesta doctor mode when a backup transfer fails or before a risky deploy.
# Captures JSON logs, EBK lines, transfer-log, and summary under a timestamped directory.
#
# Usage:
#   ./scripts/protocol-doctor.sh
#   ./scripts/protocol-doctor.sh /tmp/my-doctor-run
#   REQUIRE=rclone,restic ./scripts/protocol-doctor.sh
#   ./scripts/protocol-doctor.sh --nfs-full   # also run external NFS container suite (slow)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

NFS_FULL=0
REPORT_ROOT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --nfs-full) NFS_FULL=1; shift ;;
    -h|--help)
      sed -n '2,12p' "$0"
      exit 0
      ;;
    *)
      REPORT_ROOT="$1"
      shift
      ;;
  esac
done

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
REPORT_DIR="${REPORT_ROOT:-/tmp/edge-backup-doctor-${STAMP}}"
ROOT="${REPORT_DIR}/workspace"

PY="${REPO_ROOT}/backend/.venv/bin/python"
if [ ! -x "$PY" ]; then
  PY=python3
fi

mkdir -p "$REPORT_DIR"
echo "Silver Fiesta doctor → $REPORT_DIR"
echo "  SILVER_FIESTA_REPO=${SILVER_FIESTA_REPO:-$HOME/repo/silver-fiesta}"

EXTRA=()
[ "$NFS_FULL" -eq 1 ] && EXTRA+=(--nfs-full)

REQUIRE_ARGS=()
if [ -n "${REQUIRE:-}" ]; then
  REQUIRE_ARGS=(--require "$REQUIRE")
fi

EBK_LOG_FORMAT=json EBK_AI_STATUS=1 \
  "$PY" scripts/silver-fiesta.py \
  --doctor \
  --root "$ROOT" \
  --report-dir "$REPORT_DIR" \
  --format ai \
  "${REQUIRE_ARGS[@]}" \
  "${EXTRA[@]}" \
  2>"$REPORT_DIR/doctor.jsonl" | tee "$REPORT_DIR/doctor.ebk"

EXIT=$?
echo ""
echo "Artifacts:"
ls -la "$REPORT_DIR"
echo ""
if [ "$EXIT" -eq 0 ]; then
  echo "Doctor: all non-skipped probes passed."
elif [ "$EXIT" -eq 2 ]; then
  echo "Doctor: required protocol(s) missing — install tools or unset REQUIRE."
else
  echo "Doctor: one or more probes failed — see transfer-log.jsonl and doctor.jsonl"
  echo "  grep transfer_failed \"$REPORT_DIR/transfer-log.jsonl\""
  echo "  jq '.protocols[] | select(.ok==false)' \"$REPORT_DIR/summary.json\""
fi
exit "$EXIT"
