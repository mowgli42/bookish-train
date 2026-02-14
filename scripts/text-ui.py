#!/usr/bin/env python3
"""
Text UI for Edge Backup Dashboard — terminal alternative to the web UI.
Uses same API as web dashboard: /status, /buckets, /packages, /sources, /config, /projections.

Usage:
  python scripts/text-ui.py                    # One-shot report
  python scripts/text-ui.py --live             # Live refresh (default 3s)
  python scripts/text-ui.py --live --refresh 5 # Refresh every 5 seconds
  CATCHER_URL=http://catcher:8000 python scripts/text-ui.py

Requires: requests, rich (pip install requests rich)
"""
from __future__ import annotations

import argparse
import os
import sys
import time

try:
    import requests
except ImportError:
    print("pip install requests", file=sys.stderr)
    sys.exit(1)
try:
    from rich.console import Console, Group
    from rich.panel import Panel
    from rich.table import Table
    from rich.live import Live
    from rich import box
except ImportError:
    print("pip install rich", file=sys.stderr)
    sys.exit(1)

BASE = os.environ.get("CATCHER_URL", "http://127.0.0.1:8000").rstrip("/")
API = f"{BASE}/api/v1"
console = Console()


def fetch(path: str, params: dict | None = None) -> dict | list:
    """GET from API; return JSON or raise on error."""
    url = f"{API}{path}"
    r = requests.get(url, params=params or {}, timeout=10)
    r.raise_for_status()
    return r.json()


def fetch_safe(path: str, params: dict | None = None, default: dict | list | None = None):
    """Fetch or return default on error."""
    try:
        return fetch(path, params)
    except requests.RequestException as e:
        return default if default is not None else {"_error": str(e)}


def format_bytes(n: int) -> str:
    if not n:
        return "0 B"
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def build_report() -> Panel | Group:
    """Build full dashboard report as Rich renderable."""
    status = fetch_safe("/status", default={"components": {}, "_error": None})
    buckets_data = fetch_safe("/buckets", default={"buckets": []})
    packages = fetch_safe("/packages", default=[])
    sources = fetch_safe("/sources", default=[])
    config = fetch_safe("/config", default={"rule_sets": {}, "demo_mode": False, "unit": "days"})
    demo = config.get("demo_mode", False) or status.get("demo_mode", False)
    proj_days = 5 if not demo else None
    proj_secs = 10 if demo else None
    projections = fetch_safe("/projections", params={"days": proj_days or 5, "seconds": proj_secs}, default={"transitions": []})

    err = status.get("_error") or buckets_data.get("_error")
    if err:
        return Panel(f"[red]Error: {err}[/red]\nCATCHER_URL={BASE}", title="Edge Backup Text UI", border_style="red")

    comp = status.get("components", {})
    unit = config.get("unit", "seconds" if demo else "days")
    suffix = "s" if unit == "seconds" else "d"

    # --- Component status ---
    status_table = Table(box=None, show_header=False)
    status_table.add_column(style="dim")
    status_table.add_column()
    client_status = comp.get("client", {})
    if isinstance(client_status, dict):
        status_table.add_row("Clients", str(client_status.get("status", "—")))
    else:
        status_table.add_row("Clients", str(len(sources) if isinstance(sources, list) else "—"))
    catcher = comp.get("catcher", {})
    if isinstance(catcher, dict):
        status_table.add_row("Catcher", str(catcher.get("jobs_count", "—")))
    else:
        status_table.add_row("Catcher", "—")
    bc = comp.get("buckets", {})
    if isinstance(bc, dict):
        status_table.add_row("Buckets", f"H:{bc.get('hot',0)} W:{bc.get('warm',0)} C:{bc.get('cold',0)} O:{bc.get('offsite',0)}")
    else:
        status_table.add_row("Buckets", "—")

    # --- Buckets ---
    bucket_table = Table(title="Buckets")
    bucket_table.add_column("Tier", style="cyan")
    bucket_table.add_column("Files", justify="right")
    bucket_table.add_column("Storage", justify="right")
    buckets = buckets_data.get("buckets", [])
    for b in buckets:
        bucket_table.add_row(
            b["name"].capitalize(),
            str(b.get("count", 0)),
            format_bytes(b.get("total_bytes", 0)),
        )

    # --- Clients (sources) ---
    in_progress_by_source: dict[str, int] = {}
    last_upload_by_source: dict[str, str] = {}
    for p in packages if isinstance(packages, list) else []:
        sid = p.get("source_id", "")
        if sid:
            if p.get("status") == "in_progress":
                in_progress_by_source[sid] = in_progress_by_source.get(sid, 0) + 1
            up = p.get("updated_at") or p.get("created_at", "")
            if up and (sid not in last_upload_by_source or up > last_upload_by_source[sid]):
                last_upload_by_source[sid] = up

    client_table = Table(title="Clients")
    client_table.add_column("Source", style="cyan")
    client_table.add_column("Label")
    client_table.add_column("In Progress", justify="right")
    client_table.add_column("Last Seen")
    for s in sources if isinstance(sources, list) else []:
        sid = s.get("source_id", "")
        ls = s.get("last_seen_at", "")
        if ls:
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(ls.replace("Z", "+00:00"))
                ls = dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                pass
        client_table.add_row(
            sid,
            str(s.get("label") or "—"),
            str(in_progress_by_source.get(sid, 0)),
            ls or "—",
        )

    # --- Packages ---
    pkg_table = Table(title="Packages")
    pkg_table.add_column("Path", style="cyan", max_width=40, overflow="ellipsis")
    pkg_table.add_column("Source", width=12)
    pkg_table.add_column("Type", width=12)
    pkg_table.add_column("Bucket", width=8)
    pkg_table.add_column("Status", width=10)
    pkg_table.add_column("Age", justify="right", width=6)
    pkg_table.add_column("Progress", justify="right", width=8)
    pkg_table.add_column("Size", justify="right", width=8)
    pkg_table.add_column("Checksum", width=14, overflow="ellipsis")

    for p in (packages if isinstance(packages, list) else [])[:50]:  # limit for terminal
        age_val = p.get("age_seconds") if demo else p.get("age_days", 0)
        age_str = f"{age_val}s" if demo else f"{age_val}d"
        chk = p.get("checksum", "") or "—"
        if len(chk) > 12:
            chk = chk[:12] + "…"
        pkg_table.add_row(
            p.get("path", ""),
            p.get("source_id", ""),
            (p.get("package_type") or "user_data").replace("_", " "),
            p.get("bucket", "hot"),
            p.get("status", "pending"),
            age_str,
            f"{p.get('progress_percent', 0)}%",
            format_bytes(p.get("size_bytes") or 0),
            chk,
        )

    # --- Retention rules ---
    rule_sets = config.get("rule_sets", {})
    rules_table = Table(title="Retention Rules")
    rules_table.add_column("Type", style="cyan")
    hot_key = "hot_seconds" if demo else "hot_days"
    warm_key = "warm_seconds" if demo else "warm_days"
    cold_key = "cold_seconds" if demo else "cold_days"
    off_key = "offsite_seconds" if demo else "offsite_days"
    rules_table.add_column(f"Hot ({suffix})", justify="right")
    rules_table.add_column(f"Warm ({suffix})", justify="right")
    rules_table.add_column(f"Cold ({suffix})", justify="right")
    rules_table.add_column(f"Offsite ({suffix})", justify="right")
    rules_table.add_column("Replicate", justify="center")
    rules_table.add_column("Cache TTL (s)", justify="right")
    for ptype, rule in rule_sets.items():
        rules_table.add_row(
            ptype.replace("_", " "),
            str(rule.get(hot_key, 0)),
            str(rule.get(warm_key, 0)),
            str(rule.get(cold_key, 0)),
            str(rule.get(off_key, 0)),
            "Yes" if rule.get("replicate_to_all") else "No",
            str(rule.get("cache_seconds", "—")) if rule.get("cache_seconds") else "—",
        )

    # --- Projections ---
    transitions = projections.get("transitions", []) if isinstance(projections, dict) else []
    proj_table = Table(title="Projections (upcoming transitions)")
    proj_table.add_column("From → To")
    proj_table.add_column("Count", justify="right")
    proj_table.add_column("Jobs")
    for t in transitions:
        jobs = t.get("jobs", [])
        proj_table.add_row(
            f"{t.get('bucket_from','')} → {t.get('bucket_to','')}",
            str(t.get("count", 0)),
            ", ".join(str(j) for j in jobs[:5]) + ("…" if len(jobs) > 5 else ""),
        )

    # Assemble sections
    sections = [
        Panel(status_table, title="Component Status", border_style="green"),
        Panel(bucket_table, title="Buckets", border_style="blue"),
        Panel(client_table, title="Clients", border_style="blue"),
        Panel(pkg_table, title="Packages", border_style="blue"),
        Panel(rules_table, title="Retention Rules", border_style="blue"),
        Panel(proj_table, title="Projections", border_style="blue"),
    ]
    if demo:
        sections.append(Panel("[dim]Demo mode — retention in seconds[/dim]", title="Mode", border_style="dim"))
    deleted_count = comp.get("deleted_count", 0)
    if deleted_count > 0:
        sections.append(Panel(f"[yellow]Deleted count: {deleted_count}[/yellow]", title="Deleted", border_style="yellow"))
    sections.append(Panel("[dim]Updated data is always coming in — retention policy deletes oldest, keeps latest.[/dim]", border_style="dim"))

    return Panel(
        Group(*sections),
        title="[bold]Edge Backup Dashboard[/bold] (Text UI)",
        subtitle=f" {BASE} ",
        border_style="cyan",
        box=box.ROUNDED,
    )


def main():
    parser = argparse.ArgumentParser(description="Edge Backup Text UI — terminal alternative to web dashboard")
    parser.add_argument("--live", action="store_true", help="Live refresh mode")
    parser.add_argument("--refresh", type=int, default=3, metavar="SECS", help="Refresh interval in seconds (default: 3)")
    parser.add_argument("--save-svg", metavar="PATH", help="Save output to SVG file (for docs/screenshots)")
    args = parser.parse_args()

    if args.save_svg:
        report = build_report()
        console.print(report)
        try:
            console.save_svg(args.save_svg, title="Edge Backup Text UI")
        except Exception as e:
            console.print(f"[red]Could not save SVG: {e}[/red]")
        return

    if args.live:
        try:
            with Live(build_report(), console=console, refresh_per_second=2, screen=True) as live:
                while True:
                    time.sleep(args.refresh)
                    live.update(build_report())
        except KeyboardInterrupt:
            pass
    else:
        console.print(build_report())


if __name__ == "__main__":
    main()
