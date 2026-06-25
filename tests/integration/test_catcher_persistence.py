"""Integration tests for catcher health and SQLite persistence."""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND))


@pytest.fixture()
def client(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "catcher.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.delenv("DEMO_MODE", raising=False)

    for name in ("settings", "state", "main"):
        sys.modules.pop(name, None)

    main = importlib.import_module("main")
    return TestClient(main.app), main


def test_health_reports_persistence(client):
    test_client, _main = client
    resp = test_client.get("/health")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["status"] == "ok"
    assert payload["persistence"] == "sqlite"
    assert "jobs_count" in payload


def test_ingest_persists_across_reload(tmp_path, monkeypatch):
    db_path = tmp_path / "catcher.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    for name in ("settings", "state", "main"):
        sys.modules.pop(name, None)

    main = importlib.import_module("main")
    test_client = TestClient(main.app)
    resp = test_client.post(
        "/api/v1/ingest",
        json={
            "source_id": "persist-test",
            "path": "local/test/file.txt",
            "checksum": "deadbeef",
            "size_bytes": 10,
        },
    )
    assert resp.status_code == 200
    job_id = resp.json()["job_id"]

    for name in ("settings", "state", "main"):
        sys.modules.pop(name, None)
    main2 = importlib.import_module("main")
    test_client2 = TestClient(main2.app)
    fetched = test_client2.get(f"/api/v1/packages/{job_id}")
    assert fetched.status_code == 200
    assert fetched.json()["source_id"] == "persist-test"
