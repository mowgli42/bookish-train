"""Smoke tests for backup-agent AI output (no live catcher required for format)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_backup_agent_commands_ai():
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "backup-agent.py"), "commands", "--format", "ai"],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        check=False,
    )
    assert proc.returncode == 0
    assert "EBK" in proc.stdout or "EBK" in proc.stderr or "command=commands" in proc.stdout
