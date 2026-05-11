#!/usr/bin/env python3
"""
Run the Python client text UI demo against local and S3-style repositories.

This demo uses a filesystem-backed S3 repository so it can run without cloud
credentials. For real S3, replace S3_REPOSITORY_DIR with a future rclone/restic
destination adapter and keep S3_REPOSITORY_URI as the display label.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("pip install requests", file=sys.stderr)
    sys.exit(1)


DEFAULT_ROOT = Path(os.environ.get("EDGE_CLIENT_REPO_DEMO_ROOT", "/tmp/edge-client-repository-demo"))
DEFAULT_CATCHER_URL = os.environ.get("CATCHER_URL", "http://127.0.0.1:8000").rstrip("/")
MARKER_FILE = ".edge-client-repository-demo"


SAMPLES = {
    "Documents/family-notes.txt": "family notes\n",
    "logs/desktop-app.log": "INFO demo app uploaded\n",
    "audit/login-audit.json": '{"event":"login","result":"ok"}\n',
    "exports/budget.csv": "month,total\njan,42\n",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Demo client uploads to local and S3-style repositories.")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help=f"Demo root (default: {DEFAULT_ROOT})")
    parser.add_argument("--catcher-url", default=DEFAULT_CATCHER_URL, help=f"Catcher URL (default: {DEFAULT_CATCHER_URL})")
    parser.add_argument("--source-id", default="linux-desktop-demo", help="Client source_id for Catcher")
    parser.add_argument("--s3-uri", default="s3://edge-backup-demo/linux-desktop", help="Display URI for S3-style target")
    parser.add_argument("--keep", action="store_true", help="Reuse existing demo root instead of resetting it")
    return parser.parse_args()


def prepare_root(root: Path, keep: bool) -> None:
    if root.exists() and not keep:
        marker = root / MARKER_FILE
        if marker.exists() or root == DEFAULT_ROOT:
            shutil.rmtree(root)
        else:
            raise SystemExit(f"Refusing to reset unmarked directory: {root}")
    root.mkdir(parents=True, exist_ok=True)
    (root / MARKER_FILE).write_text("edge client repository demo\n", encoding="utf-8")


def write_samples(watch_dir: Path) -> None:
    for rel, content in SAMPLES.items():
        path = watch_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    archive_source = watch_dir / "Documents"
    archive_path = watch_dir / "exports" / "documents-package.tar.gz"
    subprocess.run(["tar", "-czf", str(archive_path), "-C", str(archive_source), "."], check=True)


def require_catcher(base_url: str) -> None:
    response = requests.get(f"{base_url}/health", timeout=5)
    response.raise_for_status()


def reset_catcher(base_url: str) -> None:
    requests.post(f"{base_url}/api/v1/demo/reset", timeout=5).raise_for_status()


def register_source(base_url: str, source_id: str) -> None:
    requests.post(
        f"{base_url}/api/v1/sources",
        json={"source_id": source_id, "label": "Linux desktop repository demo"},
        timeout=5,
    ).raise_for_status()


def run_client(root: Path, catcher_url: str, source_id: str, s3_uri: str) -> None:
    env = {
        **os.environ,
        "CATCHER_URL": catcher_url,
        "WATCH_DIR": str(root / "watch"),
        "SOURCE_ID": source_id,
        "CLIENT_TEXT_UI": "1",
        "CLIENT_RUN_ONCE": "1",
        "LOCAL_REPOSITORY_DIR": str(root / "repositories" / "local"),
        "S3_REPOSITORY_DIR": str(root / "repositories" / "s3"),
        "S3_REPOSITORY_URI": s3_uri,
    }
    subprocess.run([sys.executable, "clients/docker-client/watch_and_ingest.py"], env=env, check=True)


def verify_demo(root: Path, catcher_url: str, source_id: str) -> dict:
    expected_relative = set(SAMPLES)
    expected_relative.add("exports/documents-package.tar.gz")

    missing: list[str] = []
    for repo in ("local", "s3"):
        for rel in expected_relative:
            if not (root / "repositories" / repo / rel).exists():
                missing.append(f"{repo}/{rel}")
    if missing:
        raise RuntimeError(f"Missing repository copies: {missing}")

    response = requests.get(f"{catcher_url}/api/v1/packages", params={"source_id": source_id}, timeout=5)
    response.raise_for_status()
    packages = response.json()
    paths = {pkg["path"] for pkg in packages}
    expected_paths = {f"{repo}/{rel}" for repo in ("local", "s3") for rel in expected_relative}
    missing_paths = sorted(expected_paths - paths)
    if missing_paths:
        raise RuntimeError(f"Missing Catcher packages: {missing_paths}")
    if not all(pkg.get("status") == "completed" for pkg in packages):
        raise RuntimeError("Not all Catcher packages reached completed status")
    return {
        "root": str(root),
        "watch_dir": str(root / "watch"),
        "local_repository": str(root / "repositories" / "local"),
        "s3_repository": str(root / "repositories" / "s3"),
        "packages": packages,
    }


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    catcher_url = args.catcher_url.rstrip("/")
    require_catcher(catcher_url)
    prepare_root(root, keep=args.keep)
    write_samples(root / "watch")
    reset_catcher(catcher_url)
    register_source(catcher_url, args.source_id)

    print("=== Edge Backup Client Repository Demo ===")
    print(f"Watch dir:        {root / 'watch'}")
    print(f"Local repository: {root / 'repositories' / 'local'}")
    print(f"S3 repository:    {args.s3_uri} ({root / 'repositories' / 's3'})")
    print("")

    run_client(root, catcher_url, args.source_id, args.s3_uri)
    summary = verify_demo(root, catcher_url, args.source_id)
    summary_path = root / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print("\nDemo complete.")
    print(f"Summary: {summary_path}")
    print("Open Catcher dashboard: http://127.0.0.1:5173/#packages")
    print("Expected package paths include local/... and s3/... rows.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except requests.RequestException as exc:
        print(f"Catcher is not reachable: {exc}", file=sys.stderr)
        print("Start it with: cd backend && python3 -m uvicorn main:app --port 8000", file=sys.stderr)
        sys.exit(1)
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"Demo failed: {exc}", file=sys.stderr)
        sys.exit(1)
