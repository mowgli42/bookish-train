"""
Minimal client: watch a directory and POST new files to catcher /api/v1/ingest.
Uses polling; no durable state on edge (staging only).

Set CLIENT_TEXT_UI=1 to render a terminal table of recent package uploads.
"""
from __future__ import annotations

import os
import time
import hashlib
import logging
import sys
import shutil
from dataclasses import dataclass
from pathlib import Path

import requests

_HERE = Path(__file__).resolve().parent
for _common in (_HERE / "common", _HERE.parent / "common"):
    if _common.is_dir() and str(_common) not in sys.path:
        sys.path.insert(0, str(_common))
        break
from edge_observability import configure_observability, emit_ai_status, log_event  # noqa: E402

logger = configure_observability(os.environ.get("OTEL_SERVICE_NAME", "edge-backup-client"))

CATCHER_URL = os.environ.get("CATCHER_URL", "http://localhost:8000")
WATCH_DIR = os.environ.get("WATCH_DIR", ".")
SOURCE_ID = os.environ.get("SOURCE_ID", "docker-client")
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "5"))
CLIENT_TEXT_UI = os.environ.get("CLIENT_TEXT_UI", "").lower() in ("1", "true", "yes", "on")
MAX_UI_RECORDS = int(os.environ.get("CLIENT_TEXT_UI_LIMIT", "20"))
DEFAULT_PACKAGE_TYPE = os.environ.get("DEFAULT_PACKAGE_TYPE", "user_data")
LOCAL_REPOSITORY_DIR = os.environ.get("LOCAL_REPOSITORY_DIR", "").strip()
S3_REPOSITORY_DIR = os.environ.get("S3_REPOSITORY_DIR", "").strip()
S3_REPOSITORY_URI = os.environ.get("S3_REPOSITORY_URI", "s3://edge-backup-demo").strip()
CLIENT_RUN_ONCE = os.environ.get("CLIENT_RUN_ONCE", "").lower() in ("1", "true", "yes", "on")

SEEN: set[tuple[str, float]] = set()
UPLOADS: list["UploadRecord"] = []

PACKAGE_TYPES = {"user_data", "app_logs", "audit_logs", "business_data", "job_package", "cache"}


@dataclass
class UploadRecord:
    path: str
    package_type: str
    target: str = "catcher"
    size_bytes: int = 0
    status: str = "queued"
    progress_percent: int = 0
    checksum: str = ""
    job_id: str = ""
    message: str = ""

    @property
    def checksum_short(self) -> str:
        return f"{self.checksum[:12]}..." if len(self.checksum) > 12 else (self.checksum or "-")


def file_id(path: str, mtime: float) -> tuple[str, float]:
    return (path, mtime)


def classify_package_type(rel_path: str) -> str:
    """Map common personal-computer files to OpenSpec package_type values."""
    configured_default = DEFAULT_PACKAGE_TYPE if DEFAULT_PACKAGE_TYPE in PACKAGE_TYPES else "user_data"
    lower_path = rel_path.replace("\\", "/").lower()
    suffixes = Path(lower_path).suffixes
    suffix = suffixes[-1] if suffixes else ""
    archive_suffix = "".join(suffixes[-2:]) if len(suffixes) >= 2 else suffix

    if "/.cache/" in f"/{lower_path}" or "/cache/" in f"/{lower_path}" or suffix in {".tmp", ".temp", ".cache"}:
        return "cache"
    if "audit" in lower_path:
        return "audit_logs"
    if suffix in {".log", ".out", ".err"}:
        return "app_logs"
    if archive_suffix in {".tar.gz", ".tar.xz"} or suffix in {".zip", ".7z", ".tgz", ".tar"}:
        return "job_package"
    if suffix in {".db", ".sqlite", ".sqlite3", ".sql", ".csv", ".xlsx", ".xls"}:
        return "business_data"
    return configured_default


def format_bytes(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def set_record(record: UploadRecord, status: str, progress: int, message: str = "") -> None:
    record.status = status
    record.progress_percent = max(0, min(100, progress))
    record.message = message
    log_event(
        logger,
        logging.INFO,
        f"upload {status}",
        event_type="client_upload",
        command="upload",
        source_id=SOURCE_ID,
        path=record.path,
        package_type=record.package_type,
        status=status,
        job_id=record.job_id or None,
        station_id=record.target,
        details={"progress_percent": record.progress_percent, "message": message},
    )
    emit_ai_status(
        "upload",
        source_id=SOURCE_ID,
        path=record.path,
        target=record.target,
        package_type=record.package_type,
        status=status,
        progress_percent=record.progress_percent,
        job_id=record.job_id or None,
        message=message,
    )
    render_text_ui()


def render_text_ui() -> None:
    if not CLIENT_TEXT_UI:
        return
    recent = UPLOADS[-MAX_UI_RECORDS:]
    print("\033[2J\033[H", end="")
    print("Edge Backup Client Uploads")
    print(f"Source: {SOURCE_ID}  Watch: {os.path.abspath(WATCH_DIR)}  Catcher: {CATCHER_URL.rstrip('/')}")
    if LOCAL_REPOSITORY_DIR or S3_REPOSITORY_DIR:
        repos = []
        if LOCAL_REPOSITORY_DIR:
            repos.append(f"local={LOCAL_REPOSITORY_DIR}")
        if S3_REPOSITORY_DIR:
            repos.append(f"s3={S3_REPOSITORY_URI} ({S3_REPOSITORY_DIR})")
        print(f"Repositories: {'; '.join(repos)}")
    print("")
    headers = ("Path", "Target", "Type", "Size", "Status", "Progress", "Job", "Checksum", "Message")
    widths = (26, 8, 13, 10, 12, 8, 12, 15, 22)
    print("  ".join(h.ljust(w) for h, w in zip(headers, widths)))
    print("  ".join("-" * w for w in widths))
    for record in recent:
        row = (
            shorten(record.path, widths[0]),
            record.target,
            record.package_type,
            format_bytes(record.size_bytes),
            record.status,
            f"{record.progress_percent}%",
            record.job_id or "-",
            record.checksum_short,
            shorten(record.message, widths[8]),
        )
        print("  ".join(str(value).ljust(width) for value, width in zip(row, widths)))
    if not recent:
        print("No uploads observed yet.")
    print("", flush=True)


def shorten(value: str, width: int) -> str:
    if len(value) <= width:
        return value
    return value[: max(0, width - 3)] + "..."


def patch_package(job_id: str, progress_percent: int | None = None, status: str | None = None, checksum: str | None = None) -> None:
    body: dict[str, object] = {}
    if progress_percent is not None:
        body["progress_percent"] = max(0, min(100, progress_percent))
    if status is not None:
        body["status"] = status
    if checksum is not None:
        body["checksum"] = checksum
    if not body:
        return
    r = requests.patch(f"{CATCHER_URL.rstrip('/')}/api/v1/packages/{job_id}", json=body, timeout=10)
    r.raise_for_status()


def iter_files(base: str):
    for root, _, files in os.walk(base):
        for name in files:
            yield os.path.join(root, name)


def repository_targets(rel_path: str) -> list[tuple[str, Path, str]]:
    targets: list[tuple[str, Path, str]] = []
    if LOCAL_REPOSITORY_DIR:
        targets.append(("local", Path(LOCAL_REPOSITORY_DIR) / rel_path, f"local:{LOCAL_REPOSITORY_DIR}"))
    if S3_REPOSITORY_DIR:
        targets.append(("s3", Path(S3_REPOSITORY_DIR) / rel_path, S3_REPOSITORY_URI))
    return targets


def copy_and_verify(source: str, destination: Path, expected_checksum: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    with destination.open("rb") as f:
        actual = hashlib.sha256(f.read()).hexdigest()
    if actual != expected_checksum:
        raise OSError(f"checksum mismatch for {destination}")


def register_with_catcher(record: UploadRecord, logical_path: str, checksum: str | None) -> None:
    payload = {
        "source_id": SOURCE_ID,
        "path": logical_path,
        "size_bytes": record.size_bytes,
        "package_type": record.package_type,
    }
    if checksum:
        payload["checksum"] = checksum
    set_record(record, "registering", 75)
    r = requests.post(f"{CATCHER_URL.rstrip('/')}/api/v1/ingest", json=payload, timeout=10)
    r.raise_for_status()
    data = r.json()
    record.job_id = data.get("job_id") or ""
    set_record(record, "in_progress", 90, "registered with catcher")
    if record.job_id:
        patch_package(record.job_id, progress_percent=100, status="completed", checksum=checksum)
    set_record(record, "completed", 100, "metadata uploaded")


def scan_and_ingest() -> None:
    base = os.path.abspath(WATCH_DIR)
    if not os.path.isdir(base):
        print(f"WATCH_DIR not a directory: {base}", file=sys.stderr)
        return
    for path in iter_files(base):
        if not os.path.isfile(path):
            continue
        mtime = os.path.getmtime(path)
        key = file_id(path, mtime)
        if key in SEEN:
            continue
        SEEN.add(key)
        rel = os.path.relpath(path, base)
        size = os.path.getsize(path)
        package_type = classify_package_type(rel)
        targets = repository_targets(rel)
        if not targets:
            targets = [("catcher", Path(rel), "catcher")]
        records = [
            UploadRecord(path=rel, target=target, package_type=package_type, size_bytes=size)
            for target, _, _ in targets
        ]
        UPLOADS.extend(records)
        for record in records:
            set_record(record, "hashing", 10)
        checksum = None
        try:
            with open(path, "rb") as f:
                checksum = hashlib.sha256(f.read()).hexdigest()
            for record in records:
                record.checksum = checksum
        except OSError:
            pass
        # OpenSpec §7: checksum required when size_bytes > 0; skip files we cannot checksum
        if size > 0 and not checksum:
            for record in records:
                set_record(record, "skipped", 0, "cannot compute checksum")
            print(f"Skipped {rel}: cannot compute checksum", file=sys.stderr)
            SEEN.discard(key)
            continue
        had_failure = False
        for record, (target, destination, label) in zip(records, targets):
            logical_path = rel if target == "catcher" else f"{target}/{rel}"
            try:
                if target != "catcher":
                    set_record(record, "uploading", 35, f"copying to {label}")
                    copy_and_verify(path, destination, checksum or "")
                    set_record(record, "verified", 65, f"verified {label}")
                register_with_catcher(record, logical_path, checksum)
                print(f"Ingested {logical_path} ({package_type}) -> job_id={record.job_id}")
            except (OSError, requests.RequestException) as e:
                had_failure = True
                set_record(record, "failed", record.progress_percent, str(e))
                print(f"Failed to upload {logical_path}: {e}", file=sys.stderr)
        if had_failure:
            SEEN.discard(key)


def main() -> None:
    print(f"Watching {WATCH_DIR} -> {CATCHER_URL}", file=sys.stderr)
    render_text_ui()
    while True:
        scan_and_ingest()
        if CLIENT_RUN_ONCE:
            break
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
