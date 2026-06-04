#!/usr/bin/env python3
"""
Local provider-chain demo:

  home client -> local NAS -> Google Drive -> backup service

The demo uses local directories for every destination so it can run without
cloud credentials. If the Catcher API is reachable, it also reports each hop as
package metadata that can be watched in the dashboard or text UI.

Usage:
  python3 scripts/home-backup-chain-demo.py --no-catcher
  CATCHER_URL=http://127.0.0.1:8000 python3 scripts/home-backup-chain-demo.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import shutil
import sys
import tarfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

_COMMON = Path(__file__).resolve().parent.parent / "clients" / "common"
if str(_COMMON) not in sys.path:
    sys.path.insert(0, str(_COMMON))
from edge_observability import configure_observability, emit_ai_status, log_error, log_event  # noqa: E402

logger = configure_observability("home-backup-chain-demo")

DEFAULT_ROOT = Path(os.environ.get("EDGE_DEMO_ROOT", "/tmp/edge-backup-home-chain"))
DEFAULT_CATCHER_URL = os.environ.get("CATCHER_URL", "http://127.0.0.1:8000").rstrip("/")
MARKER_FILE = ".edge-backup-demo-root"
SOURCE_ID = "home-client"
PACKAGE_NAME = "home-client-package.tar.gz"
TRANSFER_LOG_NAME = "transfer-log.jsonl"


@dataclass(frozen=True)
class Hop:
    name: str
    source: Path
    destination: Path
    label: str
    package_type: str


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


class CatcherReporter:
    """Best-effort progress reporter for the Catcher API."""

    def __init__(self, base_url: str, enabled: bool) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_url = f"{self.base_url}/api/v1"
        self.enabled = enabled
        self._requests: Any | None = None

    def connect(self) -> None:
        if not self.enabled:
            print("Catcher reporting disabled (--no-catcher).")
            return
        try:
            import requests  # type: ignore
        except ImportError:
            print("Catcher reporting skipped: install requests to enable API reporting.")
            self.enabled = False
            return
        self._requests = requests
        try:
            response = requests.get(f"{self.base_url}/health", timeout=3)
            response.raise_for_status()
            requests.post(
                f"{self.api_url}/sources",
                json={"source_id": SOURCE_ID, "label": "Local home client demo"},
                timeout=5,
            )
            print(f"Catcher reporting enabled: {self.base_url}")
        except requests.RequestException as exc:
            print(f"Catcher reporting skipped: {exc}")
            self.enabled = False

    def start_job(self, label: str, size_bytes: int, checksum: str, package_type: str) -> str | None:
        if not self.enabled or self._requests is None:
            return None
        try:
            response = self._requests.post(
                f"{self.api_url}/ingest",
                json={
                    "source_id": SOURCE_ID,
                    "path": label,
                    "package_type": package_type,
                    "size_bytes": size_bytes,
                    "checksum": checksum,
                },
                timeout=5,
            )
            response.raise_for_status()
            job_id = response.json().get("job_id")
            if job_id:
                self.patch_job(job_id, progress_percent=0, status="in_progress")
            return job_id
        except self._requests.RequestException as exc:
            print(f"  Catcher ingest skipped for {label}: {exc}")
            return None

    def patch_job(
        self,
        job_id: str | None,
        progress_percent: int | None = None,
        status: str | None = None,
        checksum: str | None = None,
    ) -> None:
        if not job_id or not self.enabled or self._requests is None:
            return
        body: dict[str, Any] = {}
        if progress_percent is not None:
            body["progress_percent"] = progress_percent
        if status is not None:
            body["status"] = status
        if checksum is not None:
            body["checksum"] = checksum
        if not body:
            return
        try:
            response = self._requests.patch(f"{self.api_url}/packages/{job_id}", json=body, timeout=5)
            response.raise_for_status()
        except self._requests.RequestException as exc:
            print(f"  Catcher progress update skipped for {job_id}: {exc}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a local home-client -> NAS -> Google Drive -> backup-service demo."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_ROOT,
        help=f"Demo workspace root (default: {DEFAULT_ROOT})",
    )
    parser.add_argument(
        "--reuse",
        action="store_true",
        help="Reuse the existing demo workspace instead of resetting it.",
    )
    parser.add_argument(
        "--catcher-url",
        default=DEFAULT_CATCHER_URL,
        help=f"Catcher base URL for optional reporting (default: {DEFAULT_CATCHER_URL})",
    )
    parser.add_argument(
        "--no-catcher",
        action="store_true",
        help="Do not attempt to report transfer progress to Catcher.",
    )
    parser.add_argument(
        "--pause",
        type=float,
        default=0.1,
        help="Seconds to pause between copied chunks for visible progress (default: 0.1).",
    )
    parser.add_argument(
        "--log-path",
        type=Path,
        default=None,
        help=f"Local client transfer log path (default: <root>/home-client/{TRANSFER_LOG_NAME})",
    )
    parser.add_argument(
        "--resend-from-log",
        action="store_true",
        help="Read the local transfer log and resend any missing/corrupt provider copies.",
    )
    return parser.parse_args()


def prepare_root(root: Path, reset: bool) -> None:
    if reset and root.exists():
        marker = root / MARKER_FILE
        if marker.exists() or root == DEFAULT_ROOT:
            shutil.rmtree(root)
        else:
            raise SystemExit(
                f"Refusing to reset unmarked directory: {root}\n"
                f"Use --reuse or choose a demo-only path."
            )
    root.mkdir(parents=True, exist_ok=True)
    (root / MARKER_FILE).write_text("edge-backup-system demo workspace\n", encoding="utf-8")


def write_sample_home_data(home_dir: Path) -> None:
    files = {
        "Documents/taxes-2025.txt": "1040 draft\nW2: demo employer\n",
        "Documents/family-budget.csv": "month,income,expenses\njan,5000,4100\nfeb,5000,4200\n",
        "Photos/vacation/photo-001.jpg": "fake-jpeg-bytes-001\n",
        "Projects/home-inventory.json": json.dumps(
            {"items": [{"name": "laptop", "serial": "demo-001"}, {"name": "nas", "serial": "demo-002"}]},
            indent=2,
        )
        + "\n",
    }
    for relative_path, content in files.items():
        path = home_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_package(source_dir: Path, package_path: Path) -> None:
    package_path.parent.mkdir(parents=True, exist_ok=True)
    if package_path.exists():
        package_path.unlink()
    with tarfile.open(package_path, "w:gz") as archive:
        for path in sorted(p for p in source_dir.rglob("*") if p.is_file()):
            archive.add(path, arcname=path.relative_to(source_dir))


def copy_with_progress(source: Path, destination: Path, reporter: CatcherReporter, job_id: str | None, pause: float) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    total = source.stat().st_size
    copied = 0
    last_progress = -1
    with source.open("rb") as src, destination.open("wb") as dst:
        while True:
            chunk = src.read(64 * 1024)
            if not chunk:
                break
            dst.write(chunk)
            copied += len(chunk)
            progress = 100 if total == 0 else int(copied * 100 / total)
            if progress != last_progress:
                reporter.patch_job(job_id, progress_percent=progress)
                last_progress = progress
            if pause:
                time.sleep(pause)
    shutil.copystat(source, destination)


def verify_copy(source_checksum: str, destination: Path) -> str:
    destination_checksum = sha256_file(destination)
    if destination_checksum != source_checksum:
        raise RuntimeError(f"Checksum mismatch for {destination}")
    return destination_checksum


def default_transfer_log_path(root: Path) -> Path:
    return root / "home-client" / TRANSFER_LOG_NAME


def resolve_transfer_log_path(root: Path, log_path: Path | None) -> Path:
    return log_path.resolve() if log_path else default_transfer_log_path(root)


def build_hops(root: Path, package_name: str) -> list[Hop]:
    package_path = root / "home-client" / "staging" / package_name
    nas_dir = root / "local-nas" / "edge-backups"
    drive_dir = root / "google-drive" / "EdgeBackup"
    service_dir = root / "backup-service" / "vault"
    return [
        Hop(
            name="local-nas",
            source=package_path,
            destination=nas_dir / package_name,
            label=f"local-nas/{package_name}",
            package_type="user_data",
        ),
        Hop(
            name="google-drive",
            source=nas_dir / package_name,
            destination=drive_dir / package_name,
            label=f"google-drive/EdgeBackup/{package_name}",
            package_type="user_data",
        ),
        Hop(
            name="backup-service",
            source=drive_dir / package_name,
            destination=service_dir / package_name,
            label=f"backup-service/vault/{package_name}",
            package_type="business_data",
        ),
    ]


def execute_hop(
    hop: Hop,
    package_checksum: str,
    package_size: int,
    reporter: CatcherReporter,
    transfer_log: TransferLog,
    run_id: str,
    mode: str,
    pause: float,
) -> dict[str, Any]:
    print(f"Pushing package to {hop.name}: {hop.destination}")
    job_id = reporter.start_job(hop.label, package_size, package_checksum, hop.package_type)
    transfer_id = f"{package_checksum[:12]}:{hop.name}"
    transfer_log.append(
        "transfer_started",
        run_id=run_id,
        transfer_id=transfer_id,
        mode=mode,
        source_id=SOURCE_ID,
        hop=hop.name,
        source=str(hop.source),
        destination=str(hop.destination),
        label=hop.label,
        package_type=hop.package_type,
        size_bytes=package_size,
        sha256=package_checksum,
        catcher_job_id=job_id,
    )
    try:
        copy_with_progress(hop.source, hop.destination, reporter, job_id, pause)
        destination_checksum = verify_copy(package_checksum, hop.destination)
    except Exception as exc:
        reporter.patch_job(job_id, status="failed")
        transfer_log.append(
            "transfer_failed",
            run_id=run_id,
            transfer_id=transfer_id,
            mode=mode,
            source_id=SOURCE_ID,
            hop=hop.name,
            source=str(hop.source),
            destination=str(hop.destination),
            label=hop.label,
            package_type=hop.package_type,
            size_bytes=package_size,
            sha256=package_checksum,
            catcher_job_id=job_id,
            error=str(exc),
        )
        log_error(
            logger,
            f"hop {hop.name} failed: {exc}",
            event_type="transfer_failed",
            error_source="home-backup-chain-demo",
            operation=f"copy_hop:{hop.name}",
            error_message=str(exc),
            exc=exc,
            source_id=SOURCE_ID,
            package_id=job_id,
            station_id=hop.name,
            path=hop.label,
            details={"destination": str(hop.destination), "mode": mode},
        )
        emit_ai_status(
            "transfer",
            status="failed",
            source_id=SOURCE_ID,
            hop=hop.name,
            operation=f"copy_hop:{hop.name}",
            error_message=str(exc),
            error_source="home-backup-chain-demo",
        )
        raise
    reporter.patch_job(job_id, progress_percent=100, status="completed", checksum=destination_checksum)
    transfer_log.append(
        "transfer_completed",
        run_id=run_id,
        transfer_id=transfer_id,
        mode=mode,
        source_id=SOURCE_ID,
        hop=hop.name,
        source=str(hop.source),
        destination=str(hop.destination),
        label=hop.label,
        package_type=hop.package_type,
        size_bytes=hop.destination.stat().st_size,
        sha256=destination_checksum,
        catcher_job_id=job_id,
        verified=True,
    )
    print(f"  verified {hop.name} checksum: {destination_checksum}")
    return {
        "name": hop.name,
        "source": str(hop.source),
        "destination": str(hop.destination),
        "label": hop.label,
        "package_type": hop.package_type,
        "size_bytes": hop.destination.stat().st_size,
        "sha256": destination_checksum,
        "verified": True,
    }


def write_manifest(
    root: Path,
    package_checksum: str,
    package_size: int,
    hop_results: list[dict[str, Any]],
    transfer_log_path: Path,
) -> Path:
    manifest = {
        "source_id": SOURCE_ID,
        "workspace": str(root),
        "package_name": PACKAGE_NAME,
        "package_size_bytes": package_size,
        "package_sha256": package_checksum,
        "transfer_log": str(transfer_log_path),
        "flow": ["home-client", "local-nas", "google-drive", "backup-service"],
        "hops": hop_results,
    }
    manifest_path = root / "MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest_path


def run_demo(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    prepare_root(root, reset=not args.reuse)
    run_id = uuid4().hex[:12]

    home_dir = root / "home-client" / "data"
    staging_dir = root / "home-client" / "staging"
    transfer_log_path = resolve_transfer_log_path(root, args.log_path)
    transfer_log = TransferLog(transfer_log_path)

    write_sample_home_data(home_dir)
    package_path = staging_dir / PACKAGE_NAME
    create_package(home_dir, package_path)
    package_checksum = sha256_file(package_path)
    package_size = package_path.stat().st_size
    transfer_log.append(
        "package_created",
        run_id=run_id,
        source_id=SOURCE_ID,
        package_name=PACKAGE_NAME,
        package_path=str(package_path),
        package_size_bytes=package_size,
        package_sha256=package_checksum,
    )

    reporter = CatcherReporter(args.catcher_url, enabled=not args.no_catcher)
    reporter.connect()

    hops = build_hops(root, PACKAGE_NAME)

    log_event(
        logger,
        logging.INFO,
        "home backup chain demo started",
        event_type="demo_started",
        command="run",
        source_id=SOURCE_ID,
        details={"workspace": str(root), "mode": "send"},
    )
    emit_ai_status("demo_run", source_id=SOURCE_ID, status="started", workspace=str(root))

    print("\n=== Local Home Backup Chain Demo ===")
    print(f"Workspace: {root}")
    print(f"Package:   {package_path}")
    print(f"Log:       {transfer_log_path}")
    print(f"SHA-256:   {package_checksum}")
    print("")

    hop_results: list[dict[str, Any]] = []
    for hop in hops:
        hop_results.append(
            execute_hop(
                hop=hop,
                package_checksum=package_checksum,
                package_size=package_size,
                reporter=reporter,
                transfer_log=transfer_log,
                run_id=run_id,
                mode="send",
                pause=args.pause,
            )
        )

    manifest_path = write_manifest(root, package_checksum, package_size, hop_results, transfer_log_path)
    print("\nDemo complete.")
    print(f"Manifest: {manifest_path}")
    print(f"Transfer log: {transfer_log_path}")
    print("Flow: home-client -> local-nas -> google-drive -> backup-service")
    return 0


def find_verified_source(candidates: list[Path], checksum: str) -> Path | None:
    for candidate in candidates:
        if candidate.exists() and candidate.is_file() and sha256_file(candidate) == checksum:
            return candidate
    return None


def run_resend_from_log(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    transfer_log_path = resolve_transfer_log_path(root, args.log_path)
    transfer_log = TransferLog(transfer_log_path)
    package_record = transfer_log.latest_package()
    if not package_record:
        raise RuntimeError(f"No package_created record found in {transfer_log_path}")

    package_name = str(package_record.get("package_name") or PACKAGE_NAME)
    package_checksum = str(package_record["package_sha256"])
    package_size = int(package_record["package_size_bytes"])
    run_id = uuid4().hex[:12]
    hops = build_hops(root, package_name)
    candidates = [hops[0].source, *(hop.destination for hop in hops)]

    reporter = CatcherReporter(args.catcher_url, enabled=not args.no_catcher)
    reporter.connect()

    print("\n=== Resend From Local Client Log ===")
    print(f"Workspace: {root}")
    print(f"Log:       {transfer_log_path}")
    print(f"Package:   {package_name}")
    print(f"SHA-256:   {package_checksum}")
    print("")

    for hop in hops:
        if hop.destination.exists() and sha256_file(hop.destination) == package_checksum:
            transfer_log.append(
                "transfer_skipped",
                run_id=run_id,
                transfer_id=f"{package_checksum[:12]}:{hop.name}",
                mode="resend",
                source_id=SOURCE_ID,
                hop=hop.name,
                destination=str(hop.destination),
                label=hop.label,
                package_type=hop.package_type,
                size_bytes=hop.destination.stat().st_size,
                sha256=package_checksum,
                reason="destination_already_verified",
                verified=True,
            )
            print(f"Skipping {hop.name}: destination already verified")
            continue

        source = hop.source
        if not source.exists() or sha256_file(source) != package_checksum:
            recovered_source = find_verified_source(candidates, package_checksum)
            if recovered_source is None:
                raise RuntimeError(f"No verified source copy available to resend {hop.name}")
            source = recovered_source

        resend_hop = Hop(
            name=hop.name,
            source=source,
            destination=hop.destination,
            label=hop.label,
            package_type=hop.package_type,
        )
        execute_hop(
            hop=resend_hop,
            package_checksum=package_checksum,
            package_size=package_size,
            reporter=reporter,
            transfer_log=transfer_log,
            run_id=run_id,
            mode="resend",
            pause=args.pause,
        )

    print("\nResend check complete.")
    print(f"Transfer log: {transfer_log_path}")
    return 0


if __name__ == "__main__":
    try:
        parsed_args = parse_args()
        if parsed_args.resend_from_log:
            sys.exit(run_resend_from_log(parsed_args))
        sys.exit(run_demo(parsed_args))
    except KeyboardInterrupt:
        print("\nInterrupted", file=sys.stderr)
        sys.exit(130)
    except RuntimeError as exc:
        log_error(
            logger,
            f"demo failed: {exc}",
            event_type="demo_failed",
            error_source="home-backup-chain-demo",
            operation="main",
            error_message=str(exc),
            exc=exc,
        )
        print(f"Demo failed: {exc}", file=sys.stderr)
        sys.exit(1)
