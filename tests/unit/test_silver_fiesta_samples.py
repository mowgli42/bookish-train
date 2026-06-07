"""Validate checked-in Silver Fiesta sample logs for shipping."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "docs" / "samples"


def test_sample_files_exist_and_parse() -> None:
    jsonl = SAMPLES / "silver-fiesta-logs-sample.jsonl"
    ebk = SAMPLES / "silver-fiesta-ebk-sample.txt"
    transfer = SAMPLES / "silver-fiesta-transfer-log-sample.jsonl"
    assert jsonl.is_file(), "run: python3 scripts/write-silver-fiesta-samples.py"
    assert ebk.is_file()
    assert transfer.is_file()

    json_records = [json.loads(line) for line in jsonl.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert any(r.get("error_source") == "silver-fiesta" for r in json_records)
    assert any(r.get("event_type") == "transfer_failed" for r in json_records)
    assert any(r.get("event_type") == "transfer_completed" for r in json_records)

    ebk_lines = [ln for ln in ebk.read_text(encoding="utf-8").splitlines() if ln.startswith("EBK")]
    assert any("command=protocol_probe" in ln for ln in ebk_lines)
    assert any("command=protocol_summary" in ln for ln in ebk_lines)
    assert any("status=failed" in ln for ln in ebk_lines)

    transfer_records = [json.loads(line) for line in transfer.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert any(r.get("action") == "transfer_completed" for r in transfer_records)
    assert any(r.get("action") == "transfer_failed" for r in transfer_records)
    completed = [r for r in transfer_records if r.get("action") == "transfer_completed"]
    assert any(r.get("throughput_mib_s") for r in completed)


def test_write_samples_check_script() -> None:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "write-silver-fiesta-samples.py"), "--check"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
