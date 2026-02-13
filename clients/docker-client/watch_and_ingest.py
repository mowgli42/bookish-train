"""
Minimal client: watch a directory and POST new files to catcher /api/v1/ingest.
Uses polling; no durable state on edge (staging only).
"""
import os
import time
import hashlib
import sys
import requests

CATCHER_URL = os.environ.get("CATCHER_URL", "http://localhost:8000")
WATCH_DIR = os.environ.get("WATCH_DIR", ".")
SOURCE_ID = os.environ.get("SOURCE_ID", "docker-client")
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "5"))

SEEN: set[tuple[str, float]] = set()


def file_id(path: str, mtime: float) -> tuple[str, float]:
    return (path, mtime)


def scan_and_ingest() -> None:
    base = os.path.abspath(WATCH_DIR)
    if not os.path.isdir(base):
        print(f"WATCH_DIR not a directory: {base}", file=sys.stderr)
        return
    for name in os.listdir(base):
        path = os.path.join(base, name)
        if not os.path.isfile(path):
            continue
        mtime = os.path.getmtime(path)
        key = file_id(path, mtime)
        if key in SEEN:
            continue
        SEEN.add(key)
        rel = os.path.relpath(path, base)
        size = os.path.getsize(path)
        checksum = None
        try:
            with open(path, "rb") as f:
                checksum = hashlib.sha256(f.read()).hexdigest()
        except OSError:
            pass
        # OpenSpec §7: checksum required when size_bytes > 0; skip files we cannot checksum
        if size > 0 and not checksum:
            print(f"Skipped {rel}: cannot compute checksum", file=sys.stderr)
            SEEN.discard(key)
            continue
        payload = {
            "source_id": SOURCE_ID,
            "path": rel,
            "size_bytes": size,
            "checksum": checksum or "",
        }
        try:
            r = requests.post(f"{CATCHER_URL.rstrip('/')}/api/v1/ingest", json=payload, timeout=10)
            r.raise_for_status()
            data = r.json()
            print(f"Ingested {rel} -> job_id={data.get('job_id')}")
        except requests.RequestException as e:
            print(f"Failed to ingest {rel}: {e}", file=sys.stderr)


def main() -> None:
    print(f"Watching {WATCH_DIR} -> {CATCHER_URL}", file=sys.stderr)
    while True:
        scan_and_ingest()
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
