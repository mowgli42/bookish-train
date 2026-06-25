"""Unit tests for agent context export."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "clients" / "common"))

from agent_context import export_agent_context, format_agent_context_json  # noqa: E402
from transfer_log import TransferLog  # noqa: E402


def test_export_agent_context_summary(tmp_path):
    log = TransferLog(tmp_path / "transfer-log.jsonl")
    log.append("package_created", source_id="pc-1", path="/backup/pkg.tar.gz")
    log.append("transfer_completed", source_id="pc-1", verified=True)
    ctx = export_agent_context(log, source_id="pc-1")
    assert ctx["type"] == "ebk_agent_context"
    assert ctx["summary"]["healthy"] is True
    assert ctx["latest_package"]["path"] == "/backup/pkg.tar.gz"


def test_format_agent_context_json(tmp_path):
    log = TransferLog(tmp_path / "transfer-log.jsonl")
    log.append("transfer_failed", source_id="pc-2", error="timeout")
    text = format_agent_context_json(log, source_id="pc-2")
    payload = json.loads(text)
    assert payload["summary"]["failed_count"] == 1
    assert payload["summary"]["healthy"] is False
