#!/usr/bin/env python3
"""
Restic client for container prototype: backup WATCH_DIR to MinIO via restic, report to Catcher.
OpenSpec §2.2: restic for full backup (replicate_to_all / business_data).

Flow:
  1. Wait for Catcher and MinIO
  2. restic init (if repo empty)
  3. POST /ingest — register job
  4. restic backup — stream progress
  5. PATCH /packages/{id} — progress_percent, status=completed

Env: CATCHER_URL, RESTIC_REPOSITORY, RESTIC_PASSWORD, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

try:
    import requests
except ImportError:
    print("pip install requests", file=sys.stderr)
    sys.exit(1)

CATCHER_URL = os.environ.get("CATCHER_URL", "http://catcher:8000").rstrip("/")
API = f"{CATCHER_URL}/api/v1"
SOURCE_ID = os.environ.get("SOURCE_ID", "restic-client")
WATCH_DIR = os.environ.get("WATCH_DIR", "/data")
BACKUP_INTERVAL = int(os.environ.get("BACKUP_INTERVAL", "60"))


def wait_for(url: str, name: str, timeout: int = 60) -> bool:
    """Wait for service to be reachable."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=2)
            if r.status_code < 500:
                return True
        except requests.RequestException:
            pass
        print(f"  Waiting for {name}...", file=sys.stderr)
        time.sleep(2)
    return False


def restic_init() -> bool:
    """Initialize restic repo if empty."""
    try:
        subprocess.run(
            ["restic", "init"],
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "RESTIC_REPOSITORY": os.environ.get("RESTIC_REPOSITORY", "")},
        )
        return True
    except subprocess.TimeoutExpired:
        return False
    except FileNotFoundError:
        print("restic not found", file=sys.stderr)
        return False


def post_ingest(path: str, package_type: str = "business_data") -> str | None:
    """Register backup with catcher; return job_id."""
    payload = {"source_id": SOURCE_ID, "path": path, "package_type": package_type}
    try:
        r = requests.post(f"{API}/ingest", json=payload, timeout=5)
        r.raise_for_status()
        return r.json().get("job_id")
    except requests.RequestException as e:
        print(f"Ingest failed: {e}", file=sys.stderr)
        return None


def patch_package(job_id: str, progress_percent: int | None = None, status: str | None = None) -> bool:
    """Update package progress or status."""
    body = {}
    if progress_percent is not None:
        body["progress_percent"] = min(100, max(0, progress_percent))
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


def register_source() -> None:
    """Ensure source is registered."""
    try:
        requests.post(
            f"{API}/sources",
            json={"source_id": SOURCE_ID, "label": "Restic backup client (MinIO)"},
            timeout=5,
        )
    except requests.RequestException:
        pass


def run_backup() -> bool:
    """Run restic backup and report progress. RESTIC_REPOSITORY must be set."""
    repo = os.environ.get("RESTIC_REPOSITORY")
    if not repo:
        print("Set RESTIC_REPOSITORY (e.g. s3:http://minio:9000/restic)", file=sys.stderr)
        return False

    path = WATCH_DIR
    job_id = post_ingest(path, package_type="business_data")
    if not job_id:
        return False
    patch_package(job_id, status="in_progress")

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


def main() -> int:
    if not wait_for(f"{CATCHER_URL}/health", "Catcher"):
        print("Catcher not ready", file=sys.stderr)
        return 1

    # MinIO: health at /minio/health/live
    minio_url = os.environ.get("MINIO_URL", "http://minio:9000")
    if not wait_for(f"{minio_url}/minio/health/live", "MinIO"):
        print("MinIO not ready", file=sys.stderr)
        return 1

    register_source()

    # Init restic repo if needed (ignore error if already exists)
    subprocess.run(["restic", "init"], capture_output=True, timeout=30)

    print(f"Restic backup: {WATCH_DIR} -> {os.environ.get('RESTIC_REPOSITORY', '?')} (interval={BACKUP_INTERVAL}s)", file=sys.stderr)

    while True:
        if not run_backup():
            return 1
        if BACKUP_INTERVAL <= 0:
            break
        print(f"  Next backup in {BACKUP_INTERVAL}s...", file=sys.stderr)
        time.sleep(BACKUP_INTERVAL)

    return 0


if __name__ == "__main__":
    sys.exit(main())
