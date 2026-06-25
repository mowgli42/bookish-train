"""
Append-only transfer log and checksum helpers for backup clients.

Used by home-backup-chain-demo and silver-fiesta protocol validation so
troubleshooting can grep the same action names and fields across tools.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RecordListener = Callable[[dict[str, Any]], None]


class TransferLog:
    """Append-only local client log for transfer audit and resend."""

    def __init__(
        self,
        path: Path,
        *,
        listeners: list[RecordListener] | None = None,
        max_bytes: int | None = None,
    ) -> None:
        self.path = path
        self._listeners = list(listeners or [])
        self.max_bytes = max_bytes

    def add_listener(self, listener: RecordListener) -> None:
        self._listeners.append(listener)

    def remove_listener(self, listener: RecordListener) -> None:
        self._listeners = [item for item in self._listeners if item is not listener]

    def _maybe_rotate(self) -> None:
        if self.max_bytes is None or not self.path.exists():
            return
        if self.path.stat().st_size <= self.max_bytes:
            return
        rotated = self.path.with_suffix(self.path.suffix + ".1")
        if rotated.exists():
            rotated.unlink()
        self.path.rename(rotated)

    def append(self, action: str, **fields: Any) -> dict[str, Any]:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            **fields,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._maybe_rotate()
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
        for listener in self._listeners:
            listener(record)
        return record

    def read_records(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        records: list[dict[str, Any]] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise RuntimeError(f"Invalid transfer log JSON on line {line_no}: {exc}") from exc
        return records

    def filter_records(
        self,
        *,
        action: str | None = None,
        source_id: str | None = None,
        status: str | None = None,
        error_only: bool = False,
    ) -> list[dict[str, Any]]:
        records = self.read_records()
        filtered: list[dict[str, Any]] = []
        for record in records:
            if action is not None and record.get("action") != action:
                continue
            if source_id is not None and record.get("source_id") != source_id:
                continue
            if status is not None and record.get("status") != status:
                continue
            if error_only and record.get("action") not in {
                "transfer_failed",
                "package_failed",
            } and not record.get("error"):
                continue
            filtered.append(record)
        return filtered

    def latest_by_action(self, action: str) -> dict[str, Any] | None:
        for record in reversed(self.read_records()):
            if record.get("action") == action:
                return record
        return None

    def latest_package(self) -> dict[str, Any] | None:
        return self.latest_by_action("package_created")

    def failed_transfers(self, *, source_id: str | None = None) -> list[dict[str, Any]]:
        return self.filter_records(
            action="transfer_failed",
            source_id=source_id,
            error_only=True,
        )

    def recent(self, *, limit: int = 50) -> list[dict[str, Any]]:
        records = self.read_records()
        return records[-limit:]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def performance_fields(size_bytes: int, duration_sec: float, setup_sec: float = 0.0, verify_sec: float = 0.0) -> dict[str, Any]:
    """Standard performance annotations for transfer-log and EBK lines."""
    duration_ms = max(0, int(duration_sec * 1000))
    setup_ms = max(0, int(setup_sec * 1000))
    verify_ms = max(0, int(verify_sec * 1000))
    throughput_bps = int(size_bytes / duration_sec) if duration_sec > 0 and size_bytes > 0 else 0
    throughput_mib_s = round(throughput_bps / (1024 * 1024), 3) if throughput_bps else 0.0
    return {
        "size_bytes": size_bytes,
        "duration_ms": duration_ms,
        "setup_ms": setup_ms,
        "verify_ms": verify_ms,
        "throughput_bytes_per_sec": throughput_bps,
        "throughput_mib_s": throughput_mib_s,
    }
