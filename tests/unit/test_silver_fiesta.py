"""Unit tests for silver-fiesta protocol validation (no NFS containers)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "silver-fiesta.py"


def run_silver_fiesta(*args: str, env: dict | None = None) -> subprocess.CompletedProcess[str]:
    import os

    run_env = os.environ.copy()
    run_env["EBK_AI_STATUS"] = "0"
    if env:
        run_env.update(env)
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=run_env,
        check=False,
    )


def test_local_chunked_probe_passes(tmp_path: Path) -> None:
    root = tmp_path / "probe-root"
    proc = run_silver_fiesta("--root", str(root), "--protocol", "local_chunked", "--format", "json")
    assert proc.returncode == 0, proc.stderr
    summary = json.loads(proc.stdout)
    assert summary["protocols"][0]["protocol"] == "local_chunked"
    assert summary["protocols"][0]["ok"] is True
    log_path = Path(summary["transfer_log"])
    records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert any(r["action"] == "transfer_completed" for r in records)
    assert any(r.get("throughput_mib_s", 0) > 0 for r in records if r["action"] == "transfer_completed")


def test_fail_protocol_emits_transfer_failed(tmp_path: Path) -> None:
    root = tmp_path / "fail-root"
    proc = run_silver_fiesta(
        "--root",
        str(root),
        "--protocol",
        "local_chunked",
        "--fail-protocol",
        "local_chunked",
        "--format",
        "json",
    )
    assert proc.returncode == 1
    summary = json.loads(proc.stdout)
    assert summary["protocols"][0]["ok"] is False
    log_path = Path(summary["transfer_log"])
    assert "transfer_failed" in log_path.read_text(encoding="utf-8")


def test_format_ai_emits_ebk(tmp_path: Path) -> None:
    root = tmp_path / "ai-root"
    proc = run_silver_fiesta(
        "--root",
        str(root),
        "--protocol",
        "local_chunked",
        "--format",
        "ai",
        env={"EBK_AI_STATUS": "1"},
    )
    assert proc.returncode == 0
    assert "EBK" in proc.stdout
    assert "command=protocol_summary" in proc.stdout
