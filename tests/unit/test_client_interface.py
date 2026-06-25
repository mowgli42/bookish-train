"""Unit tests for the formal edge client interface."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "clients" / "common"))

from client_interface import (  # noqa: E402
    ClientConfig,
    PackageRecord,
    PackageStatus,
    StatusUpdate,
    client_interface_checks,
)
from transfer_log import TransferLog  # noqa: E402


class _StubClient:
    def __init__(self, tmp_path: Path) -> None:
        self._config = ClientConfig(
            source_id="stub-engine",
            transfer_log_path=tmp_path / "transfer-log.jsonl",
        )
        self._log = TransferLog(self._config.transfer_log_path)

    @property
    def config(self) -> ClientConfig:
        return self._config

    def transfer_log_path(self) -> Path:
        return self._config.transfer_log_path

    def run_backup(self, *, dry_run: bool = False) -> PackageRecord:
        if not dry_run:
            self._log.append("package_created", source_id=self._config.source_id, path="/tmp/pkg")
        return PackageRecord(
            package_id="pkg-1",
            source_id=self._config.source_id,
            path="/tmp/pkg",
            status=PackageStatus.COMPLETE if not dry_run else PackageStatus.SKIPPED,
        )

    def report_status(self, update: StatusUpdate) -> None:
        self._log.append(
            "status_update",
            source_id=update.source_id,
            command=update.command,
            status=update.status,
            message=update.message,
        )

    def get_recent_transfers(self, *, limit: int = 50) -> list[dict]:
        return self._log.recent(limit=limit)


def test_client_interface_checks_passes_compliant_stub(tmp_path):
    client = _StubClient(tmp_path)
    assert client_interface_checks(client) == []


def test_client_interface_checks_flags_missing_source_id(tmp_path):
    client = _StubClient(tmp_path)
    client._config.source_id = ""
    violations = client_interface_checks(client)
    assert any("source_id" in item for item in violations)


def test_stub_client_writes_transfer_log(tmp_path):
    client = _StubClient(tmp_path)
    record = client.run_backup()
    assert record.status == PackageStatus.COMPLETE
    client.report_status(StatusUpdate(source_id="stub-engine", command="backup", status="ok"))
    actions = [item["action"] for item in client.get_recent_transfers()]
    assert "package_created" in actions
    assert "status_update" in actions
