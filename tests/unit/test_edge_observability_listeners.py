"""Unit tests for guardian status listener hooks."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "clients" / "common"))

from edge_observability import (  # noqa: E402
    emit_ai_status,
    register_status_listener,
    unregister_status_listener,
)


def test_status_listener_receives_emit(monkeypatch):
    monkeypatch.setenv("EBK_AI_STATUS", "0")
    captured: list[tuple[str, dict]] = []

    def listener(command: str, fields: dict) -> None:
        captured.append((command, fields))

    register_status_listener(listener)
    try:
        emit_ai_status("backup", source_id="guardian-test", status="started")
    finally:
        unregister_status_listener(listener)

    assert captured
    assert captured[0][0] == "backup"
    assert captured[0][1]["source_id"] == "guardian-test"
