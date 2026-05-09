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
import os
import shutil
import sys
import tarfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_ROOT = Path(os.environ.get("EDGE_DEMO_ROOT", "/tmp/edge-backup-home-chain"))
DEFAULT_CATCHER_URL = os.environ.get("CATCHER_URL", "http://127.0.0.1:8000").rstrip("/")
MARKER_FILE = ".edge-backup-demo-root"
SOURCE_ID = "home-client"
PACKAGE_NAME = "home-client-package.tar.gz"


@dataclass(frozen=True)
class Hop:
    name: str
    source: Path
    destination: Path
    label: str
    package_type: str


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


def write_manifest(root: Path, package_checksum: str, package_size: int, hop_results: list[dict[str, Any]]) -> Path:
    manifest = {
        "source_id": SOURCE_ID,
        "workspace": str(root),
        "package_name": PACKAGE_NAME,
        "package_size_bytes": package_size,
        "package_sha256": package_checksum,
        "flow": ["home-client", "local-nas", "google-drive", "backup-service"],
        "hops": hop_results,
    }
    manifest_path = root / "MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest_path


def run_demo(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    prepare_root(root, reset=not args.reuse)

    home_dir = root / "home-client" / "data"
    staging_dir = root / "home-client" / "staging"
    nas_dir = root / "local-nas" / "edge-backups"
    drive_dir = root / "google-drive" / "EdgeBackup"
    service_dir = root / "backup-service" / "vault"

    write_sample_home_data(home_dir)
    package_path = staging_dir / PACKAGE_NAME
    create_package(home_dir, package_path)
    package_checksum = sha256_file(package_path)
    package_size = package_path.stat().st_size

    reporter = CatcherReporter(args.catcher_url, enabled=not args.no_catcher)
    reporter.connect()

    hops = [
        Hop(
            name="local-nas",
            source=package_path,
            destination=nas_dir / PACKAGE_NAME,
            label=f"local-nas/{PACKAGE_NAME}",
            package_type="user_data",
        ),
        Hop(
            name="google-drive",
            source=nas_dir / PACKAGE_NAME,
            destination=drive_dir / PACKAGE_NAME,
            label=f"google-drive/EdgeBackup/{PACKAGE_NAME}",
            package_type="user_data",
        ),
        Hop(
            name="backup-service",
            source=drive_dir / PACKAGE_NAME,
            destination=service_dir / PACKAGE_NAME,
            label=f"backup-service/vault/{PACKAGE_NAME}",
            package_type="business_data",
        ),
    ]

    print("\n=== Local Home Backup Chain Demo ===")
    print(f"Workspace: {root}")
    print(f"Package:   {package_path}")
    print(f"SHA-256:   {package_checksum}")
    print("")

    hop_results: list[dict[str, Any]] = []
    for hop in hops:
        print(f"Pushing package to {hop.name}: {hop.destination}")
        job_id = reporter.start_job(hop.label, package_size, package_checksum, hop.package_type)
        copy_with_progress(hop.source, hop.destination, reporter, job_id, args.pause)
        destination_checksum = verify_copy(package_checksum, hop.destination)
        reporter.patch_job(job_id, progress_percent=100, status="completed", checksum=destination_checksum)
        hop_results.append(
            {
                "name": hop.name,
                "source": str(hop.source),
                "destination": str(hop.destination),
                "label": hop.label,
                "package_type": hop.package_type,
                "size_bytes": hop.destination.stat().st_size,
                "sha256": destination_checksum,
                "verified": True,
            }
        )
        print(f"  verified {hop.name} checksum: {destination_checksum}")

    manifest_path = write_manifest(root, package_checksum, package_size, hop_results)
    print("\nDemo complete.")
    print(f"Manifest: {manifest_path}")
    print("Flow: home-client -> local-nas -> google-drive -> backup-service")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(run_demo(parse_args()))
    except KeyboardInterrupt:
        print("\nInterrupted", file=sys.stderr)
        sys.exit(130)
    except RuntimeError as exc:
        print(f"Demo failed: {exc}", file=sys.stderr)
        sys.exit(1)
