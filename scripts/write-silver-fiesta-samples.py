#!/usr/bin/env python3
"""
Write checked-in Silver Fiesta sample logs for docs and agent training.

Runs a short success probe and a simulated failure, then copies:
  docs/samples/silver-fiesta-logs-sample.jsonl   (structured JSON from stderr)
  docs/samples/silver-fiesta-ebk-sample.txt      (EBK lines from stdout)
  docs/samples/silver-fiesta-transfer-log-sample.jsonl

Usage:
  python3 scripts/write-silver-fiesta-samples.py
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "silver-fiesta.py"
SAMPLES = ROOT / "docs" / "samples"


def run_probe(
    root: Path,
    *,
    protocol: str = "local_chunked",
    fail: bool = False,
) -> tuple[list[str], list[str], Path]:
    env = {
        **dict(__import__("os").environ),
        "EBK_LOG_FORMAT": "json",
        "EBK_AI_STATUS": "1",
    }
    args = [
        sys.executable,
        str(SCRIPT),
        "--root",
        str(root),
        "--protocol",
        protocol,
        "--format",
        "ai",
    ]
    if fail:
        args.extend(["--fail-protocol", protocol])
    proc = subprocess.run(args, cwd=str(ROOT), capture_output=True, text=True, env=env, check=False)
    json_lines = [ln for ln in proc.stderr.splitlines() if ln.strip().startswith("{")]
    ebk_lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("EBK")]
    log_path = root / "client" / "transfer-log.jsonl"
    return json_lines, ebk_lines, log_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Regenerate Silver Fiesta sample log files")
    parser.add_argument("--check", action="store_true", help="Only verify samples exist and parse")
    args = parser.parse_args()

    jsonl_path = SAMPLES / "silver-fiesta-logs-sample.jsonl"
    ebk_path = SAMPLES / "silver-fiesta-ebk-sample.txt"
    transfer_path = SAMPLES / "silver-fiesta-transfer-log-sample.jsonl"

    if args.check:
        for path in (jsonl_path, ebk_path, transfer_path):
            if not path.is_file():
                print(f"missing: {path}", file=sys.stderr)
                return 1
        for line in jsonl_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                json.loads(line)
        for line in transfer_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                json.loads(line)
        assert any(ln.startswith("EBK") for ln in ebk_path.read_text(encoding="utf-8").splitlines())
        print("OK: silver-fiesta samples present and parseable")
        return 0

    SAMPLES.mkdir(parents=True, exist_ok=True)
    all_json: list[str] = []
    all_ebk: list[str] = []
    transfer_lines: list[str] = []

    with tempfile.TemporaryDirectory(prefix="sf-samples-") as tmp:
        root_ok = Path(tmp) / "success"
        json_ok, ebk_ok, log_ok = run_probe(root_ok, fail=False)
        all_json.extend(json_ok)
        all_ebk.extend(ebk_ok)
        if log_ok.is_file():
            transfer_lines.extend(log_ok.read_text(encoding="utf-8").splitlines())

        root_fail = Path(tmp) / "failure"
        json_fail, ebk_fail, log_fail = run_probe(root_fail, fail=True)
        all_json.extend(json_fail)
        all_ebk.extend(ebk_fail)
        if log_fail.is_file():
            transfer_lines.extend(log_fail.read_text(encoding="utf-8").splitlines())

    jsonl_path.write_text("\n".join(all_json) + "\n", encoding="utf-8")
    ebk_path.write_text("\n".join(all_ebk) + "\n", encoding="utf-8")
    transfer_path.write_text("\n".join(transfer_lines) + "\n", encoding="utf-8")

    print(f"Wrote {jsonl_path} ({len(all_json)} JSON lines)")
    print(f"Wrote {ebk_path} ({len(all_ebk)} EBK lines)")
    print(f"Wrote {transfer_path} ({len(transfer_lines)} transfer-log lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
