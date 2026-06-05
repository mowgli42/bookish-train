"""
Append-only transfer log and checksum helpers for backup clients.

Used by home-backup-chain-demo and silver-fiesta protocol validation so
troubleshooting can grep the same action names and fields across tools.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class TransferLog:
    """Append-only local client log for transfer audit and resend."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def append(self, action: str, **fields: Any) -> dict[str, Any]:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            **fields,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
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

    def latest_package(self) -> dict[str, Any] | None:
        for record in reversed(self.read_records()):
            if record.get("action") == "package_created":
                return record
        return None


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
