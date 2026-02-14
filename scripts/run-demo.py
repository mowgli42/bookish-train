#!/usr/bin/env python3
"""
2-minute demo: simulates Client → Catcher → Buckets flow with accelerated retention.
Requires: catcher with DEMO_MODE=1, dashboard running.

Usage:
  export DEMO_MODE=1
  uvicorn main:app --port 8000  # in backend/
  npm run dev                    # in frontend/
  python scripts/run-demo.py

Timeline (2 min):
  0:00  Reset state, register demo client
  0:15  Ingest user_data + app_logs (hot)
  0:25  Ingest cache files
  0:30  Delete cache (retention 5s expired)
  0:45  Ingest user_data backdated 35s → warm
  1:00  Ingest more cache, delete again
  1:15  Ingest audit_logs backdated 65s → cold
  1:45  Ingest business_data (replicate) + audit_logs backdated 85s
  2:00  Done — view dashboard (package types, rule sets)
"""
import os
import sys
import time

try:
    import requests
except ImportError:
    print("pip install requests", file=sys.stderr)
    sys.exit(1)

BASE = os.environ.get("CATCHER_URL", "http://127.0.0.1:8000").rstrip("/")
SOURCE = "demo-client"
DEMO_FILES = [
    {"path": "docs/readme.md", "package_type": "user_data", "size": 1200, "checksum": "a" * 64},
    {"path": "data/config.json", "package_type": "user_data", "size": 340, "checksum": "b" * 64},
    {"path": "logs/app.log", "package_type": "app_logs", "size": 5120, "checksum": "c" * 64},
    {"path": ".cache/tmp-001.bin", "package_type": "cache", "size": 256, "checksum": "d" * 64},
    {"path": ".cache/tmp-002.bin", "package_type": "cache", "size": 128, "checksum": "e" * 64},
    {"path": "audit/login-2024.json", "package_type": "audit_logs", "size": 89, "checksum": "f" * 64},
    {"path": "backup/db-snapshot.sql", "package_type": "user_data", "size": 10240, "checksum": "g" * 64},
    {"path": ".cache/session.dat", "package_type": "cache", "size": 64, "checksum": "h" * 64},
]


def post_ingest(path: str, package_type: str, size: int, checksum: str, secs_ago: int | None = None):
    headers = {}
    if secs_ago is not None:
        headers["X-Demo-Created-Secs-Ago"] = str(secs_ago)
    r = requests.post(
        f"{BASE}/api/v1/ingest",
        json={"source_id": SOURCE, "path": path, "package_type": package_type, "size_bytes": size, "checksum": checksum},
        headers=headers,
        timeout=5,
    )
    r.raise_for_status()
    return r.json().get("job_id")


def main():
    print("=== Edge Backup 2-Minute Demo ===\n")
    print("Open dashboard: http://127.0.0.1:5173")
    print("Watch: Data Flow → Buckets → Rule Set → Projections\n")

    # Reset
    requests.post(f"{BASE}/api/v1/demo/reset", timeout=5)
    print("[0:00] Reset state")

    # Register client
    requests.post(
        f"{BASE}/api/v1/sources",
        json={"source_id": SOURCE, "label": "Demo client (2-min walkthrough)"},
        timeout=5,
    )
    print(f"[0:00] Registered source: {SOURCE}")

    # 0:15 — Ingest user_data + app_logs (hot)
    for f in DEMO_FILES[:3]:
        post_ingest(f["path"], f["package_type"], f["size"], f["checksum"])
        print(f"  + {f['path']} ({f['package_type']}, hot)")
    time.sleep(15)
    print("[0:15] 3 packages in hot bucket (user_data, app_logs)")

    # 0:25 — Ingest cache
    for f in DEMO_FILES[3:5]:
        post_ingest(f["path"], f["package_type"], f["size"], f["checksum"])
        print(f"  + {f['path']} ({f['package_type']})")
    time.sleep(5)

    # 0:30 — Delete cache (5s retention)
    r = requests.delete(f"{BASE}/api/v1/jobs?tag=cache", timeout=5)
    r.raise_for_status()
    n = r.json().get("deleted", 0)
    print(f"[0:30] Deleted {n} cache/temp files (retention 5s)")
    time.sleep(15)

    # 0:45 — Ingest user_data backdated 35s → warm
    f = DEMO_FILES[6]
    post_ingest(f["path"], f["package_type"], f["size"], f["checksum"], secs_ago=35)
    print(f"[0:45] + {f['path']} ({f['package_type']}, backdated 35s → warm)")
    time.sleep(15)

    # 1:00 — Ingest cache, delete
    f = DEMO_FILES[7]
    post_ingest(f["path"], f["package_type"], f["size"], f["checksum"])
    print(f"[1:00] + {f['path']} (cache)")
    time.sleep(6)
    r = requests.delete(f"{BASE}/api/v1/jobs?tag=cache", timeout=5)
    n = r.json().get("deleted", 0)
    if n:
        print(f"[1:06] Deleted {n} cache file(s)")
    time.sleep(9)

    # 1:15 — Ingest audit_logs backdated 65s → cold
    f = DEMO_FILES[5]
    post_ingest(f["path"], f["package_type"], f["size"], f["checksum"], secs_ago=65)
    print(f"[1:15] + {f['path']} ({f['package_type']}, backdated 65s → cold)")
    time.sleep(30)

    # 1:45 — Ingest business_data (replicated to all tiers) + audit_logs backdated 85s
    post_ingest("data/customers-current.json", "business_data", 2048, "x" * 64)
    print("[1:45] + data/customers-current.json (business_data, replicate to all tiers)")
    post_ingest("audit/access-2024.json", "audit_logs", 120, "y" * 64, secs_ago=85)
    print("[1:45] + audit/access-2024.json (audit_logs, backdated 85s → cold)")

    time.sleep(15)
    print("\n[2:00] Demo complete!")
    print("Refresh dashboard to see: package types, hot/warm/cold buckets; rule sets; projections; deleted count.")
    print("GET /api/v1/status for component status.")


if __name__ == "__main__":
    try:
        r = requests.get(f"{BASE}/health", timeout=3)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"Catcher not reachable at {BASE}: {e}", file=sys.stderr)
        print("Start with: DEMO_MODE=1 uvicorn main:app --port 8000 (in backend/)", file=sys.stderr)
        sys.exit(1)
    main()
