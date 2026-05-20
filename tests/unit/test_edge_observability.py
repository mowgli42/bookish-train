"""Unit tests for structured logging and AI status lines."""
from __future__ import annotations

import json
import logging
import os
import sys
from io import StringIO
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "clients" / "common"))

from edge_observability import (  # noqa: E402
    StructuredFormatter,
    configure_observability,
    emit_ai_status,
    format_ai_line,
)


def test_format_ai_line_stable_prefix():
    line = format_ai_line("status", {"source_id": "pc-1", "status": "active"})
    assert line.startswith("EBK\t")
    assert "command=status" in line
    assert "source_id=pc-1" in line


def test_structured_formatter_json(capsys):
    os.environ["EBK_LOG_FORMAT"] = "json"
    logger = configure_observability("test-service")
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(StructuredFormatter())
    test_logger = logging.getLogger("test-formatter")
    test_logger.handlers = [handler]
    test_logger.setLevel(logging.INFO)
    test_logger.info("hello", extra={"event_type": "test_event", "service_name": "test-service"})
    payload = json.loads(stream.getvalue().strip())
    assert payload["message"] == "hello"
    assert payload["event_type"] == "test_event"
    assert payload["service.name"] == "test-service"


def test_emit_ai_status_stdout(capsys, monkeypatch):
    monkeypatch.setenv("EBK_AI_STATUS", "1")
    monkeypatch.setenv("EBK_AI_STATUS_STREAM", "stdout")
    emit_ai_status("upload", source_id="engine-1", status="completed")
    captured = capsys.readouterr().out.strip()
    assert captured.startswith("EBK\t")
    assert "command=upload" in captured
    assert "status=completed" in captured
