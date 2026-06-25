"""Unit tests for transfer log query helpers."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "clients" / "common"))

from transfer_log import TransferLog  # noqa: E402


def test_filter_records_and_failed_transfers(tmp_path):
    log = TransferLog(tmp_path / "transfer-log.jsonl")
    log.append("package_created", source_id="pc-1", path="/a")
    log.append("transfer_completed", source_id="pc-1", status="completed")
    log.append("transfer_failed", source_id="pc-1", error="timeout", status="failed")
    log.append("transfer_failed", source_id="pc-2", error="checksum")

    assert len(log.filter_records(action="package_created")) == 1
    assert len(log.failed_transfers(source_id="pc-1")) == 1
    assert log.latest_package()["path"] == "/a"


def test_transfer_log_listener_receives_records(tmp_path):
    seen: list[dict] = []
    log = TransferLog(tmp_path / "transfer-log.jsonl", listeners=[seen.append])
    log.append("probe_start", protocol="local_chunked")
    assert seen[0]["action"] == "probe_start"
    assert seen[0]["protocol"] == "local_chunked"


def test_recent_limits_records(tmp_path):
    log = TransferLog(tmp_path / "transfer-log.jsonl")
    for index in range(5):
        log.append("heartbeat", index=index)
    recent = log.recent(limit=2)
    assert len(recent) == 2
    assert recent[-1]["index"] == 4
