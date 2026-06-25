"""Integration tests: guardian monitoring + client transfer log flow."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMMON = ROOT / "clients" / "common"
sys.path.insert(0, str(COMMON))

from agent_context import export_agent_context  # noqa: E402
from client_interface import ClientConfig, PackageRecord, PackageStatus, StatusUpdate  # noqa: E402
from edge_observability import (  # noqa: E402
    emit_ai_status,
    register_status_listener,
    unregister_status_listener,
)
from transfer_log import TransferLog  # noqa: E402


class GuardianStub:
    """Minimal SnarkSentinel-style guardian that taps EBK and reads transfer logs."""

    def __init__(self, source_id: str, log_path: Path) -> None:
        self.source_id = source_id
        self.transfer_log = TransferLog(log_path)
        self.tapped: list[tuple[str, dict]] = []
        self._listener = self._on_status

    def _on_status(self, command: str, fields: dict) -> None:
        self.tapped.append((command, fields))

    def start(self) -> None:
        register_status_listener(self._listener)

    def stop(self) -> None:
        unregister_status_listener(self._listener)

    def assess(self) -> dict:
        ctx = export_agent_context(self.transfer_log, source_id=self.source_id)
        return {
            "healthy": ctx["summary"]["healthy"],
            "failed_count": ctx["summary"]["failed_count"],
            "tapped_commands": [cmd for cmd, _ in self.tapped],
        }


class BackupClientStub:
    def __init__(self, config: ClientConfig) -> None:
        self.config = config
        self.transfer_log = TransferLog(config.transfer_log_path)

    def transfer_log_path(self) -> Path:
        return self.config.transfer_log_path

    def run_backup(self, *, dry_run: bool = False) -> PackageRecord:
        emit_ai_status("backup", source_id=self.config.source_id, status="started")
        if not dry_run:
            self.transfer_log.append(
                "package_created",
                source_id=self.config.source_id,
                path="/tmp/backup.tar.gz",
                checksum="abc123",
            )
            self.transfer_log.append(
                "transfer_completed",
                source_id=self.config.source_id,
                verified=True,
            )
        emit_ai_status("backup", source_id=self.config.source_id, status="completed")
        return PackageRecord(
            package_id="pkg-1",
            source_id=self.config.source_id,
            path="/tmp/backup.tar.gz",
            status=PackageStatus.COMPLETE,
        )

    def report_status(self, update: StatusUpdate) -> None:
        self.transfer_log.append(
            "status_update",
            source_id=update.source_id,
            command=update.command,
            status=update.status,
        )

    def get_recent_transfers(self, *, limit: int = 50) -> list[dict]:
        return self.transfer_log.recent(limit=limit)


def test_guardian_monitors_client_backup_flow(tmp_path):
    log_path = tmp_path / "transfer-log.jsonl"
    source_id = "home-laptop"
    guardian = GuardianStub(source_id, log_path)
    client = BackupClientStub(
        ClientConfig(source_id=source_id, transfer_log_path=log_path),
    )

    guardian.start()
    try:
        client.run_backup()
        assessment = guardian.assess()
    finally:
        guardian.stop()

    assert assessment["healthy"] is True
    assert "backup" in assessment["tapped_commands"]
    assert guardian.tapped


def test_guardian_detects_failed_transfer(tmp_path):
    log_path = tmp_path / "transfer-log.jsonl"
    source_id = "home-laptop"
    log = TransferLog(log_path)
    log.append("transfer_failed", source_id=source_id, error="checksum mismatch")

    guardian = GuardianStub(source_id, log_path)
    assessment = guardian.assess()
    assert assessment["healthy"] is False
    assert assessment["failed_count"] == 1
