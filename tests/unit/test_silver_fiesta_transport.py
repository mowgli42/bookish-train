"""Transport probe tests with fake rclone/restic binaries (CI-safe)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "silver-fiesta.py"


def _write_fake_rclone(bin_dir: Path) -> Path:
    script = bin_dir / "rclone"
    script.write_text(
        """#!/bin/sh
if [ "$1" = "version" ]; then
  echo "rclone v1.65.0-fake"
  exit 0
fi
if [ "$1" = "copy" ]; then
  mkdir -p "$3"
  cp -a "$2/." "$3/" 2>/dev/null || { mkdir -p "$3"; cp -r "$2"/* "$3/"; }
  exit 0
fi
exit 1
""",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script


def _write_fake_restic(bin_dir: Path) -> Path:
    script = bin_dir / "restic"
    script.write_text(
        """#!/bin/sh
case "$1" in
  version) echo "restic 0.16.4-fake"; exit 0 ;;
  init|backup|check) exit 0 ;;
  *) exit 0 ;;
esac
""",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script


def run_with_path(bin_dir: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
    env["EBK_AI_STATUS"] = "0"
    env["RCLONE_BIN"] = str(bin_dir / "rclone")
    env["RESTIC_BIN"] = str(bin_dir / "restic")
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


@pytest.fixture
def fake_tools(tmp_path: Path) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_fake_rclone(bin_dir)
    _write_fake_restic(bin_dir)
    return bin_dir


def test_rclone_smoke_with_fake_binary(fake_tools: Path, tmp_path: Path) -> None:
    root = tmp_path / "rclone-smoke"
    proc = run_with_path(fake_tools, "--root", str(root), "--protocol", "rclone_smoke", "--format", "json")
    assert proc.returncode == 0, proc.stderr
    summary = json.loads(proc.stdout)
    row = summary["protocols"][0]
    assert row["protocol"] == "rclone_smoke"
    assert row["ok"] is True
    assert "fake" in row["details"].get("version_line", "").lower()


def test_rclone_transfer_with_fake_binary(fake_tools: Path, tmp_path: Path) -> None:
    root = tmp_path / "rclone-full"
    proc = run_with_path(fake_tools, "--root", str(root), "--protocol", "rclone", "--format", "json")
    assert proc.returncode == 0, proc.stderr
    summary = json.loads(proc.stdout)
    assert summary["protocols"][0]["ok"] is True
    log_path = Path(summary["transfer_log"])
    records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert any(r["action"] == "transfer_completed" and r.get("protocol") == "rclone" for r in records)


def test_restic_smoke_and_transfer_with_fake_binary(fake_tools: Path, tmp_path: Path) -> None:
    root = tmp_path / "restic"
    proc = run_with_path(
        fake_tools,
        "--root",
        str(root),
        "--protocol",
        "restic_smoke,restic",
        "--format",
        "json",
    )
    assert proc.returncode == 0, proc.stderr
    summary = json.loads(proc.stdout)
    assert len(summary["protocols"]) == 2
    assert all(p["ok"] for p in summary["protocols"])


def test_doctor_mode_includes_transport_probes(fake_tools: Path, tmp_path: Path) -> None:
    root = tmp_path / "doctor"
    report = tmp_path / "report"
    proc = run_with_path(
        fake_tools,
        "--doctor",
        "--root",
        str(root),
        "--report-dir",
        str(report),
        "--format",
        "json",
    )
    # nfs_smoke may skip if silver-fiesta repo absent; doctor still succeeds if required pass
    summary = json.loads(proc.stdout)
    names = [p["protocol"] for p in summary["protocols"]]
    assert "rclone_smoke" in names
    assert "rclone" in names
    assert "restic_smoke" in names
    assert "restic" in names
    rclone_rows = [p for p in summary["protocols"] if p["protocol"] in ("rclone_smoke", "rclone", "restic_smoke", "restic")]
    assert all(p["ok"] for p in rclone_rows)
    assert (report / "summary.json").is_file()
    assert (report / "transfer-log.jsonl").is_file()


def test_require_rclone_fails_when_missing(tmp_path: Path) -> None:
    root = tmp_path / "require"
    env = os.environ.copy()
    env["PATH"] = ""
    env["EBK_AI_STATUS"] = "0"
    env.pop("RCLONE_BIN", None)
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root), "--protocol", "rclone", "--require", "rclone", "--format", "json"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert proc.returncode == 2


@pytest.mark.skipif(not Path("/home/tprettol/repo/silver-fiesta").is_dir(), reason="silver-fiesta repo not cloned")
def test_nfs_smoke_when_repo_present(tmp_path: Path) -> None:
    root = tmp_path / "nfs"
    env = os.environ.copy()
    env["EBK_AI_STATUS"] = "0"
    env["SILVER_FIESTA_REPO"] = "/home/tprettol/repo/silver-fiesta"
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root), "--protocol", "nfs_smoke", "--format", "json"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["protocols"][0]["ok"] is True
