"""Dispatcher state with optional SQLite persistence."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from settings import Settings, get_settings


@dataclass
class DispatcherState:
    jobs: dict[str, dict] = field(default_factory=dict)
    sources: dict[str, dict] = field(default_factory=dict)
    journal: list[dict] = field(default_factory=list)
    config_snapshots: dict[str, dict] = field(default_factory=dict)
    deleted_count: int = 0
    job_id: int = 0
    journal_id: int = 0
    snapshot_id: int = 0
    _db_path: Path | None = None

    def next_job_id(self) -> str:
        self.job_id += 1
        self._persist()
        return f"job-{self.job_id}"

    def next_journal_id(self) -> str:
        self.journal_id += 1
        self._persist()
        return f"evt-{self.journal_id}"

    def next_snapshot_id(self) -> str:
        self.snapshot_id += 1
        self._persist()
        return f"cfg-{self.snapshot_id}"

    def append_journal(self, event: dict) -> None:
        self.journal.append(event)
        self._persist()

    def save_snapshot(self, snapshot: dict) -> None:
        self.config_snapshots[snapshot["snapshot_id"]] = snapshot
        self._persist()

    def set_job(self, job_id: str, job: dict) -> None:
        self.jobs[job_id] = job
        self._persist()

    def delete_job(self, job_id: str) -> dict | None:
        job = self.jobs.pop(job_id, None)
        if job is not None:
            self.deleted_count += 1
            self._persist()
        return job

    def clear_jobs(self) -> None:
        self.jobs.clear()
        self.sources.clear()
        self.deleted_count = 0
        self.job_id = 0
        self._persist()

    def set_source(self, source_id: str, source: dict) -> None:
        self.sources[source_id] = source
        self._persist()

    def _persist(self) -> None:
        if self._db_path is None:
            return
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "jobs": self.jobs,
            "sources": self.sources,
            "journal": self.journal,
            "config_snapshots": self.config_snapshots,
            "deleted_count": self.deleted_count,
            "job_id": self.job_id,
            "journal_id": self.journal_id,
            "snapshot_id": self.snapshot_id,
        }
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS dispatcher_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    payload TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "INSERT OR REPLACE INTO dispatcher_state (id, payload) VALUES (1, ?)",
                (json.dumps(payload),),
            )

    @classmethod
    def load(cls, settings: Settings | None = None) -> DispatcherState:
        settings = settings or get_settings()
        if not settings.persistence_enabled:
            return cls()

        db_path = settings.sqlite_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        state = cls(_db_path=db_path)
        if not db_path.exists():
            state._persist()
            return state

        with sqlite3.connect(db_path) as conn:
            row = conn.execute("SELECT payload FROM dispatcher_state WHERE id = 1").fetchone()
        if not row:
            state._persist()
            return state

        payload: dict[str, Any] = json.loads(row[0])
        state.jobs = payload.get("jobs", {})
        state.sources = payload.get("sources", {})
        state.journal = payload.get("journal", [])
        state.config_snapshots = payload.get("config_snapshots", {})
        state.deleted_count = int(payload.get("deleted_count", 0))
        state.job_id = int(payload.get("job_id", 0))
        state.journal_id = int(payload.get("journal_id", 0))
        state.snapshot_id = int(payload.get("snapshot_id", 0))
        return state


_STATE: DispatcherState | None = None


def get_state() -> DispatcherState:
    global _STATE
    if _STATE is None:
        _STATE = DispatcherState.load()
    return _STATE
