#!/usr/bin/env python3
"""
AI-friendly backup control CLI for terminal agents (Chaterm, OpenClaw, automation).

Emits structured status lines (EBK prefix) and JSON for agents, and uses the same
dispatcher APIs as the web/text dashboards.

Usage:
  python scripts/backup-agent.py commands
  python scripts/backup-agent.py status --format ai
  python scripts/backup-agent.py packages --source-id my-laptop --limit 10
  python scripts/backup-agent.py resume --source-id my-laptop
  python scripts/backup-agent.py journal --limit 20 --format json
  python scripts/backup-agent.py ingest --source-id pc --path local/photos/a.jpg --checksum <sha256> --size-bytes 1024

Environment:
  CATCHER_URL          Dispatcher base URL (default http://127.0.0.1:8000)
  EBK_AI_STATUS=1      Emit EBK lines on stderr/stdout for agent parsers
  OTEL_EXPORTER_OTLP_ENDPOINT   Optional SigNoz/collector endpoint
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "clients" / "common"))
sys.path.insert(0, str(ROOT))

from edge_observability import (  # noqa: E402
    configure_observability,
    emit_ai_json,
    emit_ai_status,
    format_ai_line,
    log_event,
)

try:
    import requests
except ImportError:
    print("pip install requests", file=sys.stderr)
    sys.exit(1)

BASE = os.environ.get("CATCHER_URL", "http://127.0.0.1:8000").rstrip("/")
API = f"{BASE}/api/v1"
logger = configure_observability(os.environ.get("OTEL_SERVICE_NAME", "edge-backup-agent"))


def _get(path: str, params: dict | None = None) -> dict | list:
    r = requests.get(f"{API}{path}", params=params or {}, timeout=15)
    r.raise_for_status()
    return r.json()


def _post(path: str, body: dict) -> dict:
    r = requests.post(f"{API}{path}", json=body, timeout=15)
    r.raise_for_status()
    return r.json()


def _patch(path: str, body: dict) -> dict:
    r = requests.patch(f"{API}{path}", json=body, timeout=15)
    r.raise_for_status()
    return r.json()


def output_format(args: argparse.Namespace) -> str:
    return getattr(args, "format", None) or "human"


def emit(command: str, payload: dict, fmt: str) -> None:
    if fmt == "json":
        print(json.dumps({"command": command, **payload}, default=str))
        return
    if fmt == "ai":
        if command == "commands":
            for name, desc in payload.get("commands", []):
                print(format_ai_line("command_help", name=name, description=desc))
            return
        print(format_ai_line(command, payload))
        return
    # human
    if command == "commands":
        for name, desc in payload.get("commands", []):
            print(f"  {name:12} {desc}")
        return
    print(json.dumps(payload, indent=2, default=str))


def cmd_commands(_args: argparse.Namespace) -> int:
    commands = [
        ("status", "Component status: client, catcher, buckets"),
        ("packages", "List packages (optional filters)"),
        ("package", "Get one package by id"),
        ("resume", "Unfinished switch list for a source engine"),
        ("journal", "Tail yard ledger events"),
        ("ingest", "Register a new package manifest"),
        ("patch", "Update package progress/status/checksum"),
        ("sources", "List registered sources"),
        ("buckets", "Bucket tier summary"),
        ("commands", "List available agent commands"),
    ]
    emit("commands", {"commands": commands}, output_format(_args))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    data = _get("/status")
    comp = data.get("components", {})
    payload = {
        "catcher_url": BASE,
        "demo_mode": data.get("demo_mode", False),
        "client_status": (comp.get("client") or {}).get("status", "unknown"),
        "catcher_jobs": (comp.get("catcher") or {}).get("jobs_count", 0),
        "buckets_hot": (comp.get("buckets") or {}).get("hot", 0),
        "buckets_warm": (comp.get("buckets") or {}).get("warm", 0),
        "buckets_cold": (comp.get("buckets") or {}).get("cold", 0),
        "buckets_offsite": (comp.get("buckets") or {}).get("offsite", 0),
        "deleted_count": comp.get("deleted_count", 0),
    }
    log_event(logger, logging.INFO, "backup status", event_type="agent_status", command="status", status=payload["client_status"], details=payload)
    emit("status", payload, output_format(args))
    return 0


def cmd_packages(args: argparse.Namespace) -> int:
    params: dict = {}
    if args.status:
        params["status"] = args.status
    if args.source_id:
        params["source_id"] = args.source_id
    if args.bucket:
        params["bucket"] = args.bucket
    packages = _get("/packages", params)
    if isinstance(packages, list):
        packages = packages[: args.limit]
    payload = {"count": len(packages) if isinstance(packages, list) else 0, "packages": packages}
    log_event(logger, logging.INFO, "listed packages", event_type="agent_packages", command="packages", details={"count": payload["count"]})
    if output_format(args) == "ai":
        for pkg in packages if isinstance(packages, list) else []:
            emit(
                "package_row",
                {
                    "package_id": pkg.get("package_id") or pkg.get("job_id"),
                    "source_id": pkg.get("source_id"),
                    "path": pkg.get("path"),
                    "status": pkg.get("status"),
                    "bucket": pkg.get("bucket"),
                    "progress_percent": pkg.get("progress_percent", 0),
                },
                "ai",
            )
        emit("packages", {"count": payload["count"]}, "ai")
    else:
        emit("packages", payload, output_format(args))
    return 0


def cmd_package(args: argparse.Namespace) -> int:
    pkg = _get(f"/packages/{args.package_id}")
    emit(
        "package",
        {
            "package_id": pkg.get("package_id") or pkg.get("job_id"),
            "source_id": pkg.get("source_id"),
            "path": pkg.get("path"),
            "status": pkg.get("status"),
            "bucket": pkg.get("bucket"),
            "progress_percent": pkg.get("progress_percent", 0),
            "checksum": pkg.get("checksum"),
        },
        output_format(args),
    )
    return 0


def cmd_resume(args: argparse.Namespace) -> int:
    data = _get(f"/sources/{args.source_id}/resume")
    fmt = output_format(args)
    if fmt == "ai":
        for item in data.get("switch_list", []):
            emit(
                "resume_item",
                {
                    "source_id": args.source_id,
                    "package_id": item.get("package_id"),
                    "path": item.get("path"),
                    "status": item.get("status"),
                    "station_id": item.get("station_id"),
                    "progress_percent": item.get("progress_percent", 0),
                    "last_error": item.get("last_error"),
                },
                "ai",
            )
        emit("resume", {"source_id": args.source_id, "count": data.get("count", 0)}, "ai")
    else:
        emit("resume", data, fmt)
    return 0


def cmd_journal(args: argparse.Namespace) -> int:
    params = {"limit": args.limit}
    if args.event_type:
        params["event_type"] = args.event_type
    if args.source_id:
        params["source_id"] = args.source_id
    events = _get("/journal", params)
    fmt = output_format(args)
    if fmt == "ai":
        for event in events if isinstance(events, list) else []:
            emit(
                "journal_event",
                {
                    "event_id": event.get("event_id"),
                    "event_type": event.get("event_type"),
                    "source_id": event.get("source_id"),
                    "package_id": event.get("package_id"),
                    "after_status": event.get("after_status"),
                    "error": event.get("error"),
                },
                "ai",
            )
        emit("journal", {"count": len(events) if isinstance(events, list) else 0}, "ai")
    else:
        emit("journal", {"events": events}, fmt)
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    body = {
        "source_id": args.source_id,
        "path": args.path,
        "size_bytes": args.size_bytes,
    }
    if args.checksum:
        body["checksum"] = args.checksum
    if args.package_type:
        body["package_type"] = args.package_type
    result = _post("/ingest", body)
    payload = {
        "package_id": result.get("package_id") or result.get("job_id"),
        "source_id": args.source_id,
        "path": args.path,
        "status": "pending",
    }
    log_event(
        logger,
        logging.INFO,
        "ingest registered",
        event_type="agent_ingest",
        command="ingest",
        source_id=args.source_id,
        package_id=payload["package_id"],
        path=args.path,
    )
    emit("ingest", payload, output_format(args))
    return 0


def cmd_patch(args: argparse.Namespace) -> int:
    body: dict = {}
    if args.progress is not None:
        body["progress_percent"] = args.progress
    if args.status:
        body["status"] = args.status
    if args.checksum:
        body["checksum"] = args.checksum
    if args.last_error:
        body["last_error"] = args.last_error
    result = _patch(f"/packages/{args.package_id}", body)
    emit(
        "patch",
        {
            "package_id": args.package_id,
            "status": result.get("status"),
            "progress_percent": result.get("progress_percent", 0),
        },
        output_format(args),
    )
    return 0


def cmd_sources(args: argparse.Namespace) -> int:
    sources = _get("/sources")
    emit("sources", {"sources": sources}, output_format(args))
    return 0


def cmd_buckets(args: argparse.Namespace) -> int:
    data = _get("/buckets")
    fmt = output_format(args)
    if fmt == "ai":
        for bucket in data.get("buckets", []):
            emit(
                "bucket_row",
                {
                    "name": bucket.get("name"),
                    "count": bucket.get("count", 0),
                    "total_bytes": bucket.get("total_bytes", 0),
                },
                "ai",
            )
        emit("buckets", {"tiers": len(data.get("buckets", []))}, "ai")
    else:
        emit("buckets", data, fmt)
    return 0


def main() -> int:
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument(
        "--format",
        choices=("human", "ai", "json"),
        default=os.environ.get("EBK_OUTPUT_FORMAT", "human"),
        help="Output format (human, ai=EBK lines, json)",
    )
    parser = argparse.ArgumentParser(description="Edge Backup agent CLI for AI terminals and automation")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("commands", parents=[parent], help="List commands for agent discovery").set_defaults(func=cmd_commands)

    p_status = sub.add_parser("status", parents=[parent], help="Dispatcher component status")
    p_status.set_defaults(func=cmd_status)

    p_packages = sub.add_parser("packages", parents=[parent], help="List packages")
    p_packages.add_argument("--status")
    p_packages.add_argument("--source-id")
    p_packages.add_argument("--bucket")
    p_packages.add_argument("--limit", type=int, default=50)
    p_packages.set_defaults(func=cmd_packages)

    p_pkg = sub.add_parser("package", parents=[parent], help="Get one package")
    p_pkg.add_argument("package_id")
    p_pkg.set_defaults(func=cmd_package)

    p_resume = sub.add_parser("resume", parents=[parent], help="Resume switch list for a source")
    p_resume.add_argument("--source-id", required=True)
    p_resume.set_defaults(func=cmd_resume)

    p_journal = sub.add_parser("journal", parents=[parent], help="Yard ledger tail")
    p_journal.add_argument("--limit", type=int, default=25)
    p_journal.add_argument("--event-type")
    p_journal.add_argument("--source-id")
    p_journal.set_defaults(func=cmd_journal)

    p_ingest = sub.add_parser("ingest", parents=[parent], help="Register manifest with dispatcher")
    p_ingest.add_argument("--source-id", required=True)
    p_ingest.add_argument("--path", required=True)
    p_ingest.add_argument("--checksum")
    p_ingest.add_argument("--size-bytes", type=int, default=0)
    p_ingest.add_argument("--package-type")
    p_ingest.set_defaults(func=cmd_ingest)

    p_patch = sub.add_parser("patch", parents=[parent], help="Update package progress/status")
    p_patch.add_argument("package_id")
    p_patch.add_argument("--progress", type=int)
    p_patch.add_argument("--status", choices=("pending", "in_progress", "completed", "failed"))
    p_patch.add_argument("--checksum")
    p_patch.add_argument("--last-error")
    p_patch.set_defaults(func=cmd_patch)

    p_sources = sub.add_parser("sources", parents=[parent], help="List sources")
    p_sources.set_defaults(func=cmd_sources)

    p_buckets = sub.add_parser("buckets", parents=[parent], help="Bucket summary")
    p_buckets.set_defaults(func=cmd_buckets)

    args = parser.parse_args()
    try:
        return args.func(args)
    except requests.RequestException as exc:
        err = {"error": str(exc), "catcher_url": BASE}
        log_event(logger, logging.ERROR, "agent command failed", event_type="agent_error", command=args.command, details=err)
        emit(args.command, err, output_format(args))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
