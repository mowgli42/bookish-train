"""
SQLite persistence for dispatcher control-plane state (packages/jobs, sources,
yard ledger, config snapshots, retention rule sets, demo counters).

Enable with CATCHER_SQLITE_PATH=/path/to/catcher.db or DATABASE_URL=sqlite:///path
(four slashes for absolute paths on Unix: sqlite:////var/lib/catcher.db).
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

_lock = threading.Lock()
_configured_path: str | None = None
_dirty = False


def resolve_sqlite_path() -> str | None:
    db_url = os.environ.get("DATABASE_URL", "").strip()
    if db_url.startswith("sqlite:///"):
        rest = db_url[len("sqlite:///") :]
        if rest.startswith("/"):
            return rest
        return str(Path(rest).resolve())
    p = os.environ.get("CATCHER_SQLITE_PATH", "").strip()
    if p:
        return str(Path(p).expanduser().resolve())
    return None


def configure(path: str | None) -> None:
    global _configured_path
    _configured_path = path


def is_enabled() -> bool:
    return _configured_path is not None


def mark_dirty() -> None:
    global _dirty
    if _configured_path:
        _dirty = True


def _ensure_schema(cur: sqlite3.Cursor) -> None:
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS meta (
            k TEXT PRIMARY KEY,
            v TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            payload TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sources (
            source_id TEXT PRIMARY KEY,
            payload TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS journal (
            seq INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL UNIQUE,
            payload TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS config_snapshots (
            snapshot_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            payload TEXT NOT NULL
        );
        """
    )


def init_schema(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        cur = conn.cursor()
        _ensure_schema(cur)
        conn.commit()


@dataclass
class DispatcherState:
    jobs: dict[str, dict]
    sources: dict[str, dict]
    journal: list[dict]
    config_snapshots: dict[str, dict]
    deleted_count: int
    job_id_seq: int
    journal_id_seq: int
    snapshot_id_seq: int
    rule_sets_days: dict[str, Any]
    rule_sets_seconds: dict[str, Any]


def _meta_int(cur: sqlite3.Cursor, key: str, default: int) -> int:
    cur.execute("SELECT v FROM meta WHERE k = ?", (key,))
    row = cur.fetchone()
    if not row:
        return default
    try:
        return int(row[0])
    except (TypeError, ValueError):
        return default


def _meta_json(cur: sqlite3.Cursor, key: str) -> Any | None:
    cur.execute("SELECT v FROM meta WHERE k = ?", (key,))
    row = cur.fetchone()
    if not row:
        return None
    try:
        return json.loads(row[0])
    except json.JSONDecodeError:
        return None


def _max_numeric_suffix(ids: Iterable[str], prefix: str) -> int:
    m = 0
    plen = len(prefix)
    for x in ids:
        if not x.startswith(prefix):
            continue
        tail = x[plen:]
        if tail.isdigit():
            m = max(m, int(tail))
    return m


def load_state(path: str) -> DispatcherState | None:
    """Load full dispatcher state. Returns None if the database file does not exist yet."""
    if not Path(path).exists():
        return None
    with sqlite3.connect(path) as conn:
        cur = conn.cursor()
        _ensure_schema(cur)
        cur.execute("SELECT COUNT(*) FROM jobs")
        n_jobs = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM journal")
        n_journal = cur.fetchone()[0]
        if n_jobs == 0 and n_journal == 0:
            cur.execute("SELECT COUNT(*) FROM sources")
            if cur.fetchone()[0] == 0:
                cur.execute("SELECT COUNT(*) FROM config_snapshots")
                if cur.fetchone()[0] == 0:
                    return None

        cur.execute("SELECT job_id, payload FROM jobs ORDER BY job_id")
        jobs = {row[0]: json.loads(row[1]) for row in cur.fetchall()}
        cur.execute("SELECT source_id, payload FROM sources ORDER BY source_id")
        sources = {row[0]: json.loads(row[1]) for row in cur.fetchall()}
        cur.execute("SELECT payload FROM journal ORDER BY seq")
        journal = [json.loads(row[0]) for row in cur.fetchall()]
        cur.execute("SELECT snapshot_id, payload FROM config_snapshots ORDER BY created_at, snapshot_id")
        snapshots_order = cur.fetchall()
        config_snapshots = {row[0]: json.loads(row[1]) for row in snapshots_order}

        deleted = _meta_int(cur, "deleted_count", 0)
        job_seq = _meta_int(cur, "job_id_seq", 0)
        journal_seq = _meta_int(cur, "journal_id_seq", 0)
        snapshot_seq = _meta_int(cur, "snapshot_id_seq", 0)

        if job_seq == 0:
            job_seq = _max_numeric_suffix(jobs.keys(), "job-")
        if journal_seq == 0:
            journal_seq = _max_numeric_suffix(
                [e.get("event_id", "") for e in journal if isinstance(e, dict)],
                "evt-",
            )
        if snapshot_seq == 0:
            snapshot_seq = _max_numeric_suffix(config_snapshots.keys(), "cfg-")

        rule_days = _meta_json(cur, "rule_sets_days")
        rule_seconds = _meta_json(cur, "rule_sets_seconds")
        if not isinstance(rule_days, dict):
            rule_days = {}
        if not isinstance(rule_seconds, dict):
            rule_seconds = {}

        return DispatcherState(
            jobs=jobs,
            sources=sources,
            journal=journal,
            config_snapshots=config_snapshots,
            deleted_count=deleted,
            job_id_seq=job_seq,
            journal_id_seq=journal_seq,
            snapshot_id_seq=snapshot_seq,
            rule_sets_days=rule_days,
            rule_sets_seconds=rule_seconds,
        )


def save_state(path: str, state: DispatcherState) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        cur = conn.cursor()
        _ensure_schema(cur)
        cur.execute("DELETE FROM jobs")
        cur.executemany(
            "INSERT INTO jobs (job_id, payload) VALUES (?, ?)",
            [(k, json.dumps(v, separators=(",", ":"))) for k, v in state.jobs.items()],
        )
        cur.execute("DELETE FROM sources")
        cur.executemany(
            "INSERT INTO sources (source_id, payload) VALUES (?, ?)",
            [(k, json.dumps(v, separators=(",", ":"))) for k, v in state.sources.items()],
        )
        cur.execute("DELETE FROM journal")
        for ev in state.journal:
            eid = ev.get("event_id", "")
            cur.execute(
                "INSERT INTO journal (event_id, payload) VALUES (?, ?)",
                (eid, json.dumps(ev, separators=(",", ":"))),
            )
        cur.execute("DELETE FROM config_snapshots")
        for sid, snap in state.config_snapshots.items():
            created = snap.get("created_at") or ""
            cur.execute(
                "INSERT INTO config_snapshots (snapshot_id, created_at, payload) VALUES (?, ?, ?)",
                (sid, created, json.dumps(snap, separators=(",", ":"))),
            )
        meta_rows = [
            ("deleted_count", str(state.deleted_count)),
            ("job_id_seq", str(state.job_id_seq)),
            ("journal_id_seq", str(state.journal_id_seq)),
            ("snapshot_id_seq", str(state.snapshot_id_seq)),
            ("rule_sets_days", json.dumps(state.rule_sets_days, separators=(",", ":"))),
            ("rule_sets_seconds", json.dumps(state.rule_sets_seconds, separators=(",", ":"))),
        ]
        cur.executemany(
            "INSERT INTO meta (k, v) VALUES (?, ?) ON CONFLICT(k) DO UPDATE SET v = excluded.v",
            meta_rows,
        )
        conn.commit()
    finally:
        conn.close()


def flush_if_needed(snapshot_fn: Callable[[], DispatcherState]) -> None:
    global _dirty
    if not _configured_path or not _dirty:
        return
    with _lock:
        if not _dirty:
            return
        save_state(_configured_path, snapshot_fn())
        _dirty = False
