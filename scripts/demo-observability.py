#!/usr/bin/env python3
"""
Generate sample structured logs and EBK status lines for AI agents.

Runs an in-process dispatcher scenario (no live Catcher required) plus a
client-style upload walkthrough, including one controlled transfer failure
with explicit error_source and operation fields.

Usage:
  python scripts/demo-observability.py
  python scripts/demo-observability.py --write-samples   # refresh docs/samples/
  python scripts/demo-observability.py --show-failure    # include failure in output

Sample files (for agents and documentation):
  docs/samples/agent-logs-sample.jsonl
  docs/samples/agent-ebk-sample.txt
  docs/samples/agent-log-guide.md
"""
from __future__ import annotations

import argparse
import io
import json
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "clients" / "common"))
sys.path.insert(0, str(ROOT))

from edge_observability import (  # noqa: E402
    StructuredFormatter,
    configure_observability,
    emit_ai_status,
    format_ai_line,
    log_error,
    log_event,
)

SAMPLES_DIR = ROOT / "docs" / "samples"


class CollectingHandler(logging.Handler):
    """Capture JSON log lines for sample output files."""

    def __init__(self) -> None:
        super().__init__()
        self.lines: list[str] = []
        self.setFormatter(StructuredFormatter())

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(self.formatter.format(record))


def _capture_ebk_lines(callback) -> list[str]:
    """Run callback while capturing EBK lines printed to stdout."""
    buffer = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buffer
    try:
        callback()
    finally:
        sys.stdout = old_stdout
    return [line for line in buffer.getvalue().splitlines() if line.startswith("EBK")]


def run_dispatcher_scenario(logger: logging.Logger, include_failure: bool) -> None:
    """Simulate catcher journal events agents will see in production."""
    os.environ["OTEL_SERVICE_NAME"] = "edge-backup-catcher"
    log_event(
        logger,
        logging.INFO,
        "client registered",
        event_type="client_registered",
        source_id="demo-home-client",
        actor="demo-home-client",
        details={"label": "Observability demo engine"},
    )
    emit_ai_status(
        "journal",
        event_type="client_registered",
        source_id="demo-home-client",
        status="registered",
    )
    log_event(
        logger,
        logging.INFO,
        "manifest created",
        event_type="manifest_created",
        source_id="demo-home-client",
        package_id="job-demo-1",
        station_id="local-nas",
        status="pending",
        path="local-nas/home-client-package.tar.gz",
        package_type="user_data",
        details={"size_bytes": 4096},
    )
    emit_ai_status(
        "upload",
        source_id="demo-home-client",
        path="local-nas/home-client-package.tar.gz",
        status="in_progress",
        progress_percent=55,
        job_id="job-demo-1",
    )
    if include_failure:
        log_error(
            logger,
            "transfer failed at google-drive hop",
            event_type="transfer_failed",
            error_source="home-backup-chain-demo",
            operation="copy_hop",
            error_message="checksum mismatch for /tmp/demo/google-drive/package.tar.gz",
            source_id="demo-home-client",
            package_id="job-demo-1",
            station_id="google-drive",
            path="google-drive/EdgeBackup/home-client-package.tar.gz",
            details={"hop": "google-drive", "retry_count": 1},
        )
    log_event(
        logger,
        logging.INFO,
        "transfer completed",
        event_type="transfer_completed",
        source_id="demo-home-client",
        package_id="job-demo-1",
        station_id="backup-service",
        status="completed",
        path="backup-service/vault/home-client-package.tar.gz",
        details={"verified": True},
    )
    emit_ai_status(
        "upload",
        source_id="demo-home-client",
        path="backup-service/vault/home-client-package.tar.gz",
        status="completed",
        progress_percent=100,
        job_id="job-demo-1",
    )
    log_event(
        logger,
        logging.INFO,
        "resume requested",
        event_type="resume_requested",
        source_id="demo-home-client",
        details={"count": 1 if include_failure else 0},
    )


def run_client_scenario(logger: logging.Logger) -> None:
    """Simulate docker-client upload lifecycle lines."""
    os.environ["OTEL_SERVICE_NAME"] = "edge-backup-client"
    for status, progress in (
        ("hashing", 10),
        ("uploading", 35),
        ("verified", 65),
        ("completed", 100),
    ):
        log_event(
            logger,
            logging.INFO,
            f"upload {status}",
            event_type="client_upload",
            command="upload",
            source_id="demo-home-client",
            path="Documents/taxes-2025.txt",
            package_type="user_data",
            status=status,
            station_id="local",
            details={"progress_percent": progress},
        )
        emit_ai_status(
            "upload",
            source_id="demo-home-client",
            path="Documents/taxes-2025.txt",
            target="local",
            package_type="user_data",
            status=status,
            progress_percent=progress,
        )


def write_sample_files(json_lines: list[str], ebk_lines: list[str]) -> None:
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    jsonl_path = SAMPLES_DIR / "agent-logs-sample.jsonl"
    ebk_path = SAMPLES_DIR / "agent-ebk-sample.txt"
    jsonl_path.write_text("\n".join(json_lines) + "\n", encoding="utf-8")
    ebk_path.write_text("\n".join(ebk_lines) + "\n", encoding="utf-8")
    guide = SAMPLES_DIR / "agent-log-guide.md"
    if not guide.exists():
        guide.write_text(
            "# Agent log samples\n\n"
            "See `docs/OBSERVABILITY-SIGNOZ.md` and README § AI terminals.\n\n"
            "- `agent-logs-sample.jsonl` — structured JSON logs (stderr in production)\n"
            "- `agent-ebk-sample.txt` — `EBK` tab-separated status lines for terminals\n\n"
            "Regenerate: `python scripts/demo-observability.py --write-samples`\n",
            encoding="utf-8",
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Observability demo and sample log generator")
    parser.add_argument(
        "--write-samples",
        action="store_true",
        help="Write captured output to docs/samples/ (checked into repo)",
    )
    parser.add_argument(
        "--no-failure",
        action="store_true",
        help="Omit the sample transfer_failed event",
    )
    args = parser.parse_args()
    include_failure = not args.no_failure

    os.environ["EBK_LOG_FORMAT"] = "json"
    os.environ["EBK_AI_STATUS"] = "1"

    collector = CollectingHandler()
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(collector)
    root.setLevel(logging.INFO)

    logger = logging.getLogger("edge-backup-demo")
    ebk_lines: list[str] = []

    def run_all() -> None:
        run_dispatcher_scenario(logger, include_failure)
        run_client_scenario(logger)

    ebk_lines.extend(_capture_ebk_lines(run_all))
    # EBK lines may also be emitted while stdout was not redirected for collector path;
    # re-run capture only for EBK by duplicating emit calls is already in run_all via capture.
    # Also append one reference line for command discovery.
    ebk_lines.insert(0, format_ai_line("demo_start", {"scenario": "observability", "failure_included": include_failure}))

    print("=== Edge Backup Observability Demo ===\n")
    print("Structured JSON logs (stderr in production):\n")
    for line in collector.lines:
        print(line)
    print("\nEBK status lines (stdout for agents):\n")
    for line in ebk_lines:
        print(line)

    print("\n--- How agents should read these logs ---")
    print("JSON: parse each line; use event_type, error_source, operation, error_message on failures.")
    print("EBK:  lines start with 'EBK'; split on tabs; fields are key=value.")
    print("Example failure filter: grep '\"event_type\":\"transfer_failed\"' or grep '^EBK.*error'")

    if args.write_samples:
        write_sample_files(collector.lines, ebk_lines)
        print(f"\nWrote samples to {SAMPLES_DIR}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
