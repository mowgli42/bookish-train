#!/usr/bin/env python3
"""
Populate the catcher with mock data so you can see the dashboard working.
Prerequisites: catcher running on CATCHER_URL (default http://localhost:8000).
Usage: python scripts/seed-demo-data.py [--source SOURCE_ID]
"""
import argparse
import json
import os
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("Install requests: pip install requests", file=sys.stderr)
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST = REPO_ROOT / "tests" / "fixtures" / "mock-data" / "MANIFEST.json"
DEFAULT_SOURCE = "demo-seed"


def main() -> None:
    p = argparse.ArgumentParser(description="Seed catcher with mock data from MANIFEST.json")
    p.add_argument("--source", default=DEFAULT_SOURCE, help="source_id for ingested files")
    p.add_argument("--url", default=os.environ.get("CATCHER_URL", "http://localhost:8000"), help="Catcher base URL")
    args = p.parse_args()

    if not MANIFEST.exists():
        print(f"MANIFEST not found: {MANIFEST}", file=sys.stderr)
        sys.exit(1)

    base = args.url.rstrip("/")
    manifest = json.loads(MANIFEST.read_text())
    files = manifest.get("files", [])

    # Register source
    try:
        r = requests.post(f"{base}/api/v1/sources", json={"source_id": args.source, "label": "Demo seed"}, timeout=5)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"Failed to register source: {e}", file=sys.stderr)
        sys.exit(1)

    # Ingest each file from manifest
    for f in files:
        payload = {
            "source_id": args.source,
            "path": f["path"],
            "checksum": f.get("checksum", ""),
            "size_bytes": f.get("size_bytes", 0),
            "tier_hint": f.get("tier_hint"),
        }
        try:
            r = requests.post(f"{base}/api/v1/ingest", json=payload, timeout=5)
            r.raise_for_status()
            data = r.json()
            print(f"  {f['path']} -> {data.get('job_id', '?')}")
        except requests.RequestException as e:
            print(f"  {f['path']} FAILED: {e}", file=sys.stderr)

    print(f"\nDone. Open http://localhost:5173 and click Refresh to see {len(files)} jobs.")


if __name__ == "__main__":
    main()
