"""
Formal client interface for edge backup engines.

External guardians (e.g. SnarkSentinel) can type-hint against EdgeClientProtocol,
mock implementations in tests, and validate compliance via client_interface_checks().
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


class PackageStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    FAILED = "failed"
    SKIPPED = "skipped"


class TransferStatus(str, Enum):
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ClientConfig:
    """Minimal configuration shared by edge clients."""

    source_id: str
    catcher_url: str = ""
    watch_dir: Path | None = None
    transfer_log_path: Path | None = None
    package_type: str = "user_data"
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> ClientConfig:
        import os

        watch = os.environ.get("WATCH_DIR", "").strip()
        log_path = os.environ.get("EBK_TRANSFER_LOG", "").strip()
        return cls(
            source_id=os.environ.get("SOURCE_ID", "edge-client"),
            catcher_url=os.environ.get("CATCHER_URL", ""),
            watch_dir=Path(watch) if watch else None,
            transfer_log_path=Path(log_path) if log_path else None,
            package_type=os.environ.get("EBK_PACKAGE_TYPE", "user_data"),
        )


@dataclass
class PackageRecord:
    package_id: str
    source_id: str
    path: str
    size_bytes: int = 0
    checksum: str = ""
    package_type: str = "user_data"
    status: PackageStatus = PackageStatus.PENDING
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TransferRecord:
    transfer_id: str
    source_id: str
    action: str
    protocol: str = ""
    station_id: str = ""
    path: str = ""
    status: TransferStatus = TransferStatus.STARTED
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StatusUpdate:
    source_id: str
    command: str
    status: str
    message: str = ""
    package_id: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class EdgeClientProtocol(Protocol):
    """Contract for edge backup engines consumed by guardians and dispatchers."""

    @property
    def config(self) -> ClientConfig: ...

    def transfer_log_path(self) -> Path: ...

    def run_backup(self, *, dry_run: bool = False) -> PackageRecord: ...

    def report_status(self, update: StatusUpdate) -> None: ...

    def get_recent_transfers(self, *, limit: int = 50) -> list[dict[str, Any]]: ...


def client_interface_checks(client: EdgeClientProtocol) -> list[str]:
    """Return a list of compliance violations (empty when compliant)."""
    violations: list[str] = []
    if not client.config.source_id:
        violations.append("config.source_id is required")
    try:
        path = client.transfer_log_path()
    except Exception as exc:  # noqa: BLE001
        violations.append(f"transfer_log_path() raised: {exc}")
    else:
        if not isinstance(path, Path):
            violations.append("transfer_log_path() must return pathlib.Path")
    for method_name in ("run_backup", "report_status", "get_recent_transfers"):
        if not callable(getattr(client, method_name, None)):
            violations.append(f"missing callable: {method_name}")
    return violations
