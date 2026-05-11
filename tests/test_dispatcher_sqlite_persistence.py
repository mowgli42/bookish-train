"""SQLite persistence for the dispatcher (Catcher): survives process restart."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest
from starlette.testclient import TestClient

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


def _reload_backend_modules(
    monkeypatch,
    *,
    catcher_sqlite: Path | None = None,
    database_url: str | None = None,
):
    monkeypatch.delenv("CATCHER_SQLITE_PATH", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    if catcher_sqlite is not None:
        monkeypatch.setenv("CATCHER_SQLITE_PATH", str(catcher_sqlite))
    if database_url is not None:
        monkeypatch.setenv("DATABASE_URL", database_url)
    backend_dir = Path(__file__).resolve().parent.parent / "backend"
    str_backend = str(backend_dir)
    if str_backend not in sys.path:
        sys.path.insert(0, str_backend)
    import sqlite_persistence

    importlib.reload(sqlite_persistence)
    import main

    return importlib.reload(main)


def test_packages_survive_client_restart(tmp_path, monkeypatch):
    db = tmp_path / "dispatcher.sqlite3"
    main = _reload_backend_modules(monkeypatch, catcher_sqlite=db)
    with TestClient(main.app) as client:
        r = client.post(
            "/api/v1/ingest",
            json={
                "source_id": "engine-a",
                "path": "local/docs/notes.txt",
                "checksum": "a" * 64,
                "size_bytes": 10,
                "package_type": "user_data",
            },
        )
        assert r.status_code == 200
        job_id = r.json()["job_id"]
        client.patch(f"/api/v1/packages/{job_id}", json={"progress_percent": 42})
        assert len(client.get("/api/v1/journal").json()) >= 1

    assert db.exists()

    main2 = _reload_backend_modules(monkeypatch, catcher_sqlite=db)
    with TestClient(main2.app) as client2:
        pkgs = client2.get("/api/v1/packages").json()
        assert len(pkgs) == 1
        assert pkgs[0]["job_id"] == job_id
        assert pkgs[0]["progress_percent"] == 42
        journal = client2.get("/api/v1/journal", params={"limit": 500}).json()
        assert any(e.get("event_type") == "manifest_created" for e in journal)


def test_database_url_sqlite_absolute(tmp_path, monkeypatch):
    db = tmp_path / "from_url.db"
    url = f"sqlite:////{db.resolve()}"
    main = _reload_backend_modules(monkeypatch, database_url=url)
    with TestClient(main.app) as client:
        client.post(
            "/api/v1/ingest",
            json={"source_id": "s", "path": "p", "checksum": "b" * 64, "size_bytes": 1},
        )
    assert db.is_file()
