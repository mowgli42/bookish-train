#!/usr/bin/env python3
"""
Prototype: Run restic or rclone backups and report progress to the Edge Backup Catcher API.
The Catcher tracks metadata only (path, size, checksum, progress); actual storage is handled
by restic (dedup backup) or rclone (transfer between tiers).

Flow:
  1. POST /ingest — register the backup job
  2. Run restic backup or rclone copy
  3. PATCH /packages/{id} — update progress_percent during transfer
  4. PATCH /packages/{id} — set status=completed, checksum when done
  5. Monitor via: python scripts/text-ui.py --live

Usage:
  # Mock mode (no restic/rclone needed) — simulates 0–100% over 10s
  python scripts/restic-rclone-backup.py --mock --path backup/2024-01

  # Restic backup (requires restic + RESTIC_REPOSITORY)
  RESTIC_REPOSITORY=s3:s3.amazonaws.com/my-bucket python scripts/restic-rclone-backup.py --tool restic --path /data

  # Rclone copy (requires rclone config)
  python scripts/restic-rclone-backup.py --tool rclone --from /local/data --to remote:bucket/path

In another terminal, watch progress:
  python scripts/text-ui.py --live
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time

try:
    import requests
except ImportError:
    print("pip install requests", file=sys.stderr)
    sys.exit(1)

BASE = os.environ.get("CATCHER_URL", "http://127.0.0.1:8000").rstrip("/")
API = f"{BASE}/api/v1"
DEFAULT_SOURCE = "restic-rclone-client"


def post_ingest(path: str, source_id: str, size_bytes: int = 0, checksum: str | None = None, package_type: str = "user_data") -> str | None:
    """Register backup with catcher; return job_id."""
    payload = {"source_id": source_id, "path": path, "package_type": package_type}
    if size_bytes > 0 and checksum:
        payload["size_bytes"] = size_bytes
        payload["checksum"] = checksum
    try:
        r = requests.post(f"{API}/ingest", json=payload, timeout=5)
        r.raise_for_status()
        return r.json().get("job_id")
    except requests.RequestException as e:
        print(f"Ingest failed: {e}", file=sys.stderr)
        return None


def patch_package(job_id: str, progress_percent: int | None = None, checksum: str | None = None, status: str | None = None) -> bool:
    """Update package progress or status."""
    body = {}
    if progress_percent is not None:
        body["progress_percent"] = min(100, max(0, progress_percent))
    if checksum is not None:
        body["checksum"] = checksum
    if status is not None:
        body["status"] = status
    if not body:
        return True
    try:
        r = requests.patch(f"{API}/packages/{job_id}", json=body, timeout=5)
        r.raise_for_status()
        return True
    except requests.RequestException as e:
        print(f"Patch failed: {e}", file=sys.stderr)
        return False


def register_source(source_id: str) -> None:
    """Ensure source is registered."""
    try:
        requests.post(
            f"{API}/sources",
            json={"source_id": source_id, "label": "Restic/Rclone backup client"},
            timeout=5,
        )
    except requests.RequestException:
        pass


# --- Mock mode (simulate progress) ---
def run_mock(path: str, source_id: str, duration: int = 10) -> bool:
    """Simulate backup progress for demos."""
    job_id = post_ingest(path, source_id, size_bytes=1024000, checksum="a" * 64)
    if not job_id:
        return False
    patch_package(job_id, status="in_progress")
    steps = min(duration, 20)
    for i in range(steps + 1):
        pct = int(100 * i / steps)
        patch_package(job_id, progress_percent=pct)
        print(f"  [{path}] {pct}%")
        if i < steps:
            time.sleep(duration / steps)
    patch_package(job_id, progress_percent=100, status="completed")
    print(f"  [{path}] completed -> {job_id}")
    return True


# --- Restic mode ---
def run_restic(path: str, source_id: str) -> bool:
    """Run restic backup and report progress. RESTIC_REPOSITORY must be set."""
    repo = os.environ.get("RESTIC_REPOSITORY")
    if not repo:
        print("Set RESTIC_REPOSITORY (e.g. s3:s3.amazonaws.com/bucket)", file=sys.stderr)
        return False
    job_id = post_ingest(path, source_id, package_type="business_data")
    if not job_id:
        return False
    patch_package(job_id, status="in_progress")
    # restic backup --json outputs JSON lines; status has percent_done
    try:
        proc = subprocess.Popen(
            ["restic", "backup", path, "--json"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        last_pct = 0
        for line in proc.stdout or []:
            try:
                msg = json.loads(line)
                if msg.get("message_type") == "status":
                    pct = int(msg.get("percent_done", 0) * 100)
                    if pct > last_pct and pct <= 100:
                        patch_package(job_id, progress_percent=pct)
                        last_pct = pct
                        print(f"  [{path}] {pct}%")
                elif msg.get("message_type") == "summary":
                    patch_package(job_id, progress_percent=100, status="completed")
                    print(f"  [{path}] completed -> {job_id}")
            except json.JSONDecodeError:
                pass
        proc.wait()
        if proc.returncode != 0:
            patch_package(job_id, status="failed")
            return False
        return True
    except FileNotFoundError:
        print("restic not found. Install: https://restic.net/", file=sys.stderr)
        return False


# --- Rclone mode ---
def run_rclone(from_path: str, to_path: str, source_id: str) -> bool:
    """Run rclone copy and report progress. Parses --progress output."""
    path_label = f"{from_path} → {to_path}"
    job_id = post_ingest(path_label, source_id, package_type="user_data")
    if not job_id:
        return False
    patch_package(job_id, status="in_progress")
    # rclone copy --progress outputs "Transferred: 1.2 GiB / 5.0 GiB, 24%"
    progress_re = re.compile(r"(\d+)%")
    try:
        proc = subprocess.Popen(
            ["rclone", "copy", from_path, to_path, "--progress", "--stats-one-line"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        last_pct = 0
        for line in proc.stdout or []:
            m = progress_re.search(line)
            if m:
                pct = int(m.group(1))
                if pct > last_pct and pct <= 100:
                    patch_package(job_id, progress_percent=pct)
                    last_pct = pct
                    print(f"  [{path_label}] {pct}%")
        proc.wait()
        if proc.returncode != 0:
            patch_package(job_id, status="failed")
            return False
        patch_package(job_id, progress_percent=100, status="completed")
        print(f"  [{path_label}] completed -> {job_id}")
        return True
    except FileNotFoundError:
        print("rclone not found. Install: https://rclone.org/", file=sys.stderr)
        return False


def main() -> int:
    p = argparse.ArgumentParser(description="Run restic/rclone backup and report to Catcher API")
    p.add_argument("--tool", choices=["mock", "restic", "rclone"], default="mock", help="Tool (default: mock)")
    p.add_argument("--mock", action="store_true", help="Shorthand for --tool mock")
    p.add_argument("--path", help="Path to backup (restic/mock)")
    p.add_argument("--from", dest="from_path", metavar="FROM", help="Source path (rclone)")
    p.add_argument("--to", dest="to_path", metavar="TO", help="Destination path (rclone)")
    p.add_argument("--source", default=DEFAULT_SOURCE, help=f"source_id (default: {DEFAULT_SOURCE})")
    p.add_argument("--duration", type=int, default=10, help="Mock mode: duration in seconds (default: 10)")
    args = p.parse_args()

    source_id = args.source
    register_source(source_id)
    tool = "mock" if args.mock else args.tool

    if tool == "mock":
        path = args.path or "backup/mock-demo"
        print(f"Mock backup: {path} (duration={args.duration}s)")
        return 0 if run_mock(path, source_id, args.duration) else 1

    if tool == "restic":
        path = args.path or "."
        print(f"Restic backup: {path} -> {os.environ.get('RESTIC_REPOSITORY', '?')}")
        return 0 if run_restic(path, source_id) else 1

    if tool == "rclone":
        if not args.from_path or not args.to_path:
            print("rclone requires --from and --to", file=sys.stderr)
            return 1
        print(f"Rclone copy: {args.from_path} -> {args.to_path}")
        return 0 if run_rclone(args.from_path, args.to_path, source_id) else 1

    return 1


if __name__ == "__main__":
    sys.exit(main())
