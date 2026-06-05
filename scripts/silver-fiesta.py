#!/usr/bin/env python3
"""
Silver Fiesta — transfer protocol validation for bookish-train.

Proves that configured file-transfer paths work and records performance
annotations using the same structured logging and transfer-log.jsonl format
as home-backup-chain-demo (for backup troubleshooting and AI agents).

Protocols probed (when available):
  - local_chunked   Chunked copy + SHA-256 verify (engine default)
  - local_rsync     rsync -a when installed
  - rclone_smoke    rclone binary + version (fast; no data copy)
  - rclone          Local-to-local rclone copy + checksum
  - restic_smoke    restic binary + version (fast)
  - restic          restic init/backup/check in a temp repository
  - nfs_smoke       External silver-fiesta: compose + pytest collect
  - nfs_full        External silver-fiesta: make test-lightweight (slow)

Usage:
  python3 scripts/silver-fiesta.py
  python3 scripts/silver-fiesta.py --doctor              # all probes for incident triage
  ./scripts/protocol-doctor.sh                           # same + saves logs under /tmp
  python3 scripts/silver-fiesta.py --protocol rclone_smoke,rclone,restic_smoke,restic
  python3 scripts/silver-fiesta.py --require rclone,restic  # fail if tools missing
  SILVER_FIESTA_REPO=~/repo/silver-fiesta python3 scripts/silver-fiesta.py --nfs-smoke

Requires: rich (pip install -r scripts/requirements-text-ui.txt)
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

_COMMON = Path(__file__).resolve().parent.parent / "clients" / "common"
if str(_COMMON) not in sys.path:
    sys.path.insert(0, str(_COMMON))

from edge_observability import configure_observability, emit_ai_status, log_error, log_event  # noqa: E402
from transfer_log import TransferLog, performance_fields, sha256_file  # noqa: E402

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich import box
except ImportError:
    print("pip install rich (see scripts/requirements-text-ui.txt)", file=sys.stderr)
    sys.exit(1)

logger = configure_observability("silver-fiesta")
console = Console()

ERROR_SOURCE = "silver-fiesta"
SOURCE_ID = "silver-fiesta-probe"
DEFAULT_ROOT = Path(os.environ.get("EDGE_PROTOCOL_ROOT", "/tmp/edge-backup-protocol-verify"))
SILVER_FIESTA_REPO = Path(os.environ.get("SILVER_FIESTA_REPO", Path.home() / "repo/silver-fiesta")).expanduser()
TRANSFER_LOG_NAME = "transfer-log.jsonl"
MARKER_FILE = ".edge-backup-protocol-root"
PROBE_SIZES = (
    ("smoke", 64 * 1024),
    ("standard", 2 * 1024 * 1024),
)

DOCTOR_PROTOCOLS = [
    "local_chunked",
    "local_rsync",
    "rclone_smoke",
    "rclone",
    "restic_smoke",
    "restic",
    "nfs_smoke",
]


def tool_binary(name: str) -> str | None:
    """Resolve CLI tool path (RCLONE_BIN / RESTIC_BIN override for tests)."""
    override = os.environ.get(f"{name.upper()}_BIN", "").strip()
    if override:
        path = Path(override)
        return str(path) if path.is_file() else override
    found = shutil.which(name)
    return found


@dataclass
class ProtocolResult:
    protocol: str
    setup_ok: bool
    transfer_ok: bool
    skipped: bool = False
    skip_reason: str = ""
    error_message: str = ""
    size_bytes: int = 0
    setup_ms: int = 0
    duration_ms: int = 0
    verify_ms: int = 0
    throughput_mib_s: float = 0.0
    sha256: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.skipped and self.setup_ok and self.transfer_ok


ProbeFn = Callable[[Path, TransferLog, str], ProtocolResult]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate bookish-train file transfer protocols (Silver Fiesta harness)."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_ROOT,
        help=f"Workspace for probe payloads (default: {DEFAULT_ROOT})",
    )
    parser.add_argument(
        "--reuse",
        action="store_true",
        help="Reuse workspace instead of resetting it.",
    )
    parser.add_argument(
        "--protocol",
        default="auto",
        help="Comma-separated protocols or 'auto' for all available (default: auto)",
    )
    parser.add_argument(
        "--log-path",
        type=Path,
        default=None,
        help=f"Transfer log path (default: <root>/client/{TRANSFER_LOG_NAME})",
    )
    parser.add_argument(
        "--format",
        choices=("human", "ai", "json"),
        default="human",
        help="Terminal output: rich UI, EBK lines, or JSON summary",
    )
    parser.add_argument(
        "--nfs-smoke",
        action="store_true",
        help="Include nfs_smoke probe (silver-fiesta compose + pytest collect).",
    )
    parser.add_argument(
        "--nfs-full",
        action="store_true",
        help="Run full silver-fiesta NFS suite (slow; needs nfs/nfsd modules).",
    )
    parser.add_argument(
        "--fail-protocol",
        metavar="NAME",
        help="Simulate failure on this protocol (debugging demo).",
    )
    parser.add_argument(
        "--doctor",
        action="store_true",
        help="Run full triage suite (chunked, rsync, rclone/restic smoke+transfer, nfs_smoke).",
    )
    parser.add_argument(
        "--require",
        metavar="PROTO,...",
        default="",
        help="Comma-separated protocols that must not be skipped (exit 2 if missing).",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=None,
        help="With --doctor: also write doctor.jsonl, doctor.ebk, and summary.json here.",
    )
    return parser.parse_args()


def prepare_root(root: Path, reuse: bool) -> None:
    if not reuse and root.exists():
        marker = root / MARKER_FILE
        if marker.exists() or root == DEFAULT_ROOT:
            shutil.rmtree(root)
        else:
            raise SystemExit(
                f"Refusing to reset unmarked directory: {root}\nUse --reuse or a demo-only path."
            )
    root.mkdir(parents=True, exist_ok=True)
    (root / MARKER_FILE).write_text("edge-backup transfer protocol validation workspace\n", encoding="utf-8")


def write_payload(path: Path, size_bytes: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    chunk = b"EBK-PROTOCOL-PROBE-" * 4096
    remaining = size_bytes
    with path.open("wb") as handle:
        while remaining > 0:
            block = chunk[: min(len(chunk), remaining)]
            handle.write(block)
            remaining -= len(block)


def copy_chunked(source: Path, destination: Path, pause: float = 0.0) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    total = source.stat().st_size
    copied = 0
    with source.open("rb") as src, destination.open("wb") as dst:
        while True:
            chunk = src.read(64 * 1024)
            if not chunk:
                break
            dst.write(chunk)
            copied += len(chunk)
            if pause:
                time.sleep(pause)
    shutil.copystat(source, destination)


def log_probe_start(transfer_log: TransferLog, run_id: str, protocol: str) -> None:
    transfer_log.append(
        "protocol_setup_started",
        run_id=run_id,
        source_id=SOURCE_ID,
        protocol=protocol,
        actor=ERROR_SOURCE,
    )
    log_event(
        logger,
        logging.INFO,
        f"protocol setup started: {protocol}",
        event_type="protocol_setup_started",
        command="protocol_probe",
        source_id=SOURCE_ID,
        actor=ERROR_SOURCE,
        details={"protocol": protocol, "run_id": run_id},
    )
    emit_ai_status(
        "protocol_probe",
        source_id=SOURCE_ID,
        protocol=protocol,
        phase="setup",
        status="started",
        run_id=run_id,
    )


def log_transfer_started(transfer_log: TransferLog, run_id: str, protocol: str, **extra: Any) -> str:
    transfer_id = f"{run_id}:{protocol}"
    transfer_log.append(
        "transfer_started",
        run_id=run_id,
        transfer_id=transfer_id,
        mode="protocol_probe",
        source_id=SOURCE_ID,
        hop=protocol,
        protocol=protocol,
        actor=ERROR_SOURCE,
        **extra,
    )
    emit_ai_status(
        "transfer",
        source_id=SOURCE_ID,
        protocol=protocol,
        phase="transfer",
        status="started",
        transfer_id=transfer_id,
        run_id=run_id,
    )
    return transfer_id


def finish_result(
    transfer_log: TransferLog,
    run_id: str,
    result: ProtocolResult,
    transfer_id: str,
    *,
    source: str = "",
    destination: str = "",
) -> ProtocolResult:
    perf = performance_fields(
        result.size_bytes,
        result.duration_ms / 1000.0,
        setup_sec=result.setup_ms / 1000.0,
        verify_sec=result.verify_ms / 1000.0,
    )
    base = {
        "run_id": run_id,
        "transfer_id": transfer_id,
        "mode": "protocol_probe",
        "source_id": SOURCE_ID,
        "hop": result.protocol,
        "protocol": result.protocol,
        "actor": ERROR_SOURCE,
        "setup_ok": result.setup_ok,
        **perf,
    }
    if source:
        base["source"] = source
    if destination:
        base["destination"] = destination
    if result.sha256:
        base["sha256"] = result.sha256

    if result.skipped:
        transfer_log.append(
            "transfer_skipped",
            reason=result.skip_reason,
            **base,
        )
        emit_ai_status(
            "protocol_probe",
            source_id=SOURCE_ID,
            protocol=result.protocol,
            status="skipped",
            reason=result.skip_reason,
            run_id=run_id,
        )
        return result

    if result.ok:
        transfer_log.append("transfer_completed", verified=True, **base)
        log_event(
            logger,
            logging.INFO,
            f"protocol {result.protocol} OK",
            event_type="transfer_completed",
            command="protocol_probe",
            source_id=SOURCE_ID,
            station_id=result.protocol,
            status="completed",
            details={**perf, "protocol": result.protocol},
        )
        emit_ai_status(
            "protocol_probe",
            source_id=SOURCE_ID,
            protocol=result.protocol,
            status="completed",
            setup_ok=True,
            transfer_ok=True,
            run_id=run_id,
            **perf,
        )
    else:
        transfer_log.append(
            "transfer_failed",
            error=result.error_message,
            **base,
        )
        log_error(
            logger,
            f"protocol {result.protocol} failed: {result.error_message}",
            event_type="transfer_failed",
            error_source=ERROR_SOURCE,
            operation=f"protocol_probe:{result.protocol}",
            error_message=result.error_message,
            command="protocol_probe",
            source_id=SOURCE_ID,
            station_id=result.protocol,
            details={"protocol": result.protocol, **perf},
        )
        emit_ai_status(
            "protocol_probe",
            source_id=SOURCE_ID,
            protocol=result.protocol,
            status="failed",
            setup_ok=result.setup_ok,
            transfer_ok=result.transfer_ok,
            error_message=result.error_message,
            run_id=run_id,
            **perf,
        )
    return result


def probe_local_chunked(root: Path, transfer_log: TransferLog, run_id: str) -> ProtocolResult:
    protocol = "local_chunked"
    log_probe_start(transfer_log, run_id, protocol)
    workspace = root / "payloads" / protocol
    source = workspace / "source.bin"
    destination = workspace / "destination.bin"
    result = ProtocolResult(protocol=protocol, setup_ok=True, transfer_ok=False)
    setup_start = time.perf_counter()
    try:
        write_payload(source, PROBE_SIZES[1][1])
        result.size_bytes = source.stat().st_size
        result.sha256 = sha256_file(source)
        result.setup_ms = int((time.perf_counter() - setup_start) * 1000)
        transfer_log.append(
            "protocol_setup_ok",
            run_id=run_id,
            source_id=SOURCE_ID,
            protocol=protocol,
            package_path=str(source),
            package_size_bytes=result.size_bytes,
            package_sha256=result.sha256,
            setup_ms=result.setup_ms,
        )
    except OSError as exc:
        result.setup_ok = False
        result.error_message = str(exc)
        return finish_result(transfer_log, run_id, result, f"{run_id}:{protocol}")

    transfer_id = log_transfer_started(
        transfer_log,
        run_id,
        protocol,
        source=str(source),
        destination=str(destination),
        size_bytes=result.size_bytes,
        sha256=result.sha256,
    )
    try:
        start = time.perf_counter()
        copy_chunked(source, destination)
        result.duration_ms = int((time.perf_counter() - start) * 1000)
        verify_start = time.perf_counter()
        if sha256_file(destination) != result.sha256:
            raise RuntimeError("checksum mismatch after chunked copy")
        result.verify_ms = int((time.perf_counter() - verify_start) * 1000)
        result.transfer_ok = True
        result.throughput_mib_s = performance_fields(result.size_bytes, result.duration_ms / 1000.0)[
            "throughput_mib_s"
        ]
    except Exception as exc:
        result.error_message = str(exc)
    return finish_result(
        transfer_log, run_id, result, transfer_id, source=str(source), destination=str(destination)
    )


def probe_tool_smoke(
    tool: str,
    protocol: str,
    _root: Path,
    transfer_log: TransferLog,
    run_id: str,
) -> ProtocolResult:
    """Fast binary check (like nfs_smoke for the external NFS harness)."""
    result = ProtocolResult(protocol=protocol, setup_ok=False, transfer_ok=False)
    binary = tool_binary(tool)
    if not binary:
        result.skipped = True
        result.skip_reason = f"{tool} not installed"
        return finish_result(transfer_log, run_id, result, f"{run_id}:{protocol}")

    log_probe_start(transfer_log, run_id, protocol)
    transfer_id = log_transfer_started(
        transfer_log,
        run_id,
        protocol,
        destination=binary,
        size_bytes=0,
    )
    start = time.perf_counter()
    try:
        proc = subprocess.run([binary, "version"], capture_output=True, text=True, check=False, timeout=30)
        result.duration_ms = int((time.perf_counter() - start) * 1000)
        result.setup_ms = result.duration_ms
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or f"{tool} version exit {proc.returncode}")
        version_line = (proc.stdout or proc.stderr or "").strip().splitlines()[0]
        result.setup_ok = True
        result.transfer_ok = True
        result.details["binary"] = binary
        result.details["version_line"] = version_line[:200]
        transfer_log.append(
            "protocol_setup_ok",
            run_id=run_id,
            source_id=SOURCE_ID,
            protocol=protocol,
            tool=tool,
            binary=binary,
            version_line=version_line[:200],
            setup_ms=result.setup_ms,
        )
    except Exception as exc:
        result.error_message = str(exc)
    return finish_result(transfer_log, run_id, result, transfer_id, destination=binary)


def probe_rclone_smoke(root: Path, transfer_log: TransferLog, run_id: str) -> ProtocolResult:
    return probe_tool_smoke("rclone", "rclone_smoke", root, transfer_log, run_id)


def probe_restic_smoke(root: Path, transfer_log: TransferLog, run_id: str) -> ProtocolResult:
    return probe_tool_smoke("restic", "restic_smoke", root, transfer_log, run_id)


def probe_local_rsync(root: Path, transfer_log: TransferLog, run_id: str) -> ProtocolResult:
    protocol = "local_rsync"
    result = ProtocolResult(protocol=protocol, setup_ok=False, transfer_ok=False)
    if not tool_binary("rsync"):
        result.skipped = True
        result.skip_reason = "rsync not installed"
        return finish_result(transfer_log, run_id, result, f"{run_id}:{protocol}")

    log_probe_start(transfer_log, run_id, protocol)
    workspace = root / "payloads" / protocol
    source_dir = workspace / "src"
    dest_dir = workspace / "dst"
    source_file = source_dir / "probe.bin"
    setup_start = time.perf_counter()
    try:
        write_payload(source_file, PROBE_SIZES[0][1])
        result.size_bytes = source_file.stat().st_size
        result.sha256 = sha256_file(source_file)
        result.setup_ms = int((time.perf_counter() - setup_start) * 1000)
        result.setup_ok = True
        transfer_log.append(
            "protocol_setup_ok",
            run_id=run_id,
            source_id=SOURCE_ID,
            protocol=protocol,
            package_path=str(source_file),
            package_size_bytes=result.size_bytes,
            package_sha256=result.sha256,
            setup_ms=result.setup_ms,
        )
    except OSError as exc:
        result.error_message = str(exc)
        return finish_result(transfer_log, run_id, result, f"{run_id}:{protocol}")

    transfer_id = log_transfer_started(
        transfer_log,
        run_id,
        protocol,
        source=str(source_dir),
        destination=str(dest_dir),
        size_bytes=result.size_bytes,
        sha256=result.sha256,
    )
    try:
        start = time.perf_counter()
        proc = subprocess.run(
            ["rsync", "-a", "--delete", f"{source_dir}/", f"{dest_dir}/"],
            capture_output=True,
            text=True,
            check=False,
        )
        result.duration_ms = int((time.perf_counter() - start) * 1000)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or f"rsync exit {proc.returncode}")
        dest_file = dest_dir / "probe.bin"
        verify_start = time.perf_counter()
        if sha256_file(dest_file) != result.sha256:
            raise RuntimeError("checksum mismatch after rsync")
        result.verify_ms = int((time.perf_counter() - verify_start) * 1000)
        result.transfer_ok = True
        result.throughput_mib_s = performance_fields(result.size_bytes, result.duration_ms / 1000.0)[
            "throughput_mib_s"
        ]
    except Exception as exc:
        result.error_message = str(exc)
    return finish_result(
        transfer_log, run_id, result, transfer_id, source=str(source_dir), destination=str(dest_dir)
    )


def probe_rclone(root: Path, transfer_log: TransferLog, run_id: str) -> ProtocolResult:
    protocol = "rclone"
    result = ProtocolResult(protocol=protocol, setup_ok=False, transfer_ok=False)
    rclone_bin = tool_binary("rclone")
    if not rclone_bin:
        result.skipped = True
        result.skip_reason = "rclone not installed"
        return finish_result(transfer_log, run_id, result, f"{run_id}:{protocol}")

    log_probe_start(transfer_log, run_id, protocol)
    workspace = root / "payloads" / protocol
    source_dir = workspace / "from"
    dest_dir = workspace / "to"
    source_file = source_dir / "probe.bin"
    setup_start = time.perf_counter()
    try:
        write_payload(source_file, PROBE_SIZES[1][1])
        result.size_bytes = source_file.stat().st_size
        result.sha256 = sha256_file(source_file)
        result.setup_ms = int((time.perf_counter() - setup_start) * 1000)
        result.setup_ok = True
        transfer_log.append(
            "protocol_setup_ok",
            run_id=run_id,
            source_id=SOURCE_ID,
            protocol=protocol,
            package_path=str(source_file),
            package_size_bytes=result.size_bytes,
            package_sha256=result.sha256,
            setup_ms=result.setup_ms,
        )
    except OSError as exc:
        result.error_message = str(exc)
        return finish_result(transfer_log, run_id, result, f"{run_id}:{protocol}")

    transfer_id = log_transfer_started(
        transfer_log,
        run_id,
        protocol,
        source=str(source_dir),
        destination=str(dest_dir),
        size_bytes=result.size_bytes,
        sha256=result.sha256,
    )
    try:
        start = time.perf_counter()
        proc = subprocess.run(
            [rclone_bin, "copy", str(source_dir), str(dest_dir), "--stats-one-line", "--stats", "1s"],
            capture_output=True,
            text=True,
            check=False,
        )
        result.duration_ms = int((time.perf_counter() - start) * 1000)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or f"rclone exit {proc.returncode}")
        dest_file = dest_dir / source_file.name
        if not dest_file.exists():
            dest_file = dest_dir / "probe.bin"
        verify_start = time.perf_counter()
        if sha256_file(dest_file) != result.sha256:
            raise RuntimeError("checksum mismatch after rclone copy")
        result.verify_ms = int((time.perf_counter() - verify_start) * 1000)
        result.transfer_ok = True
        result.throughput_mib_s = performance_fields(result.size_bytes, result.duration_ms / 1000.0)[
            "throughput_mib_s"
        ]
        result.details["rclone_stderr_tail"] = (proc.stderr or "")[-200:]
    except Exception as exc:
        result.error_message = str(exc)
    return finish_result(
        transfer_log, run_id, result, transfer_id, source=str(source_dir), destination=str(dest_dir)
    )


def probe_restic(root: Path, transfer_log: TransferLog, run_id: str) -> ProtocolResult:
    protocol = "restic"
    result = ProtocolResult(protocol=protocol, setup_ok=False, transfer_ok=False)
    restic_bin = tool_binary("restic")
    if not restic_bin:
        result.skipped = True
        result.skip_reason = "restic not installed"
        return finish_result(transfer_log, run_id, result, f"{run_id}:{protocol}")

    log_probe_start(transfer_log, run_id, protocol)
    workspace = root / "payloads" / protocol
    data_dir = workspace / "data"
    repo_dir = workspace / "restic-repo"
    setup_start = time.perf_counter()
    env = os.environ.copy()
    env["RESTIC_REPOSITORY"] = str(repo_dir)
    env.setdefault("RESTIC_PASSWORD", "edge-backup-protocol-probe")
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        write_payload(data_dir / "probe.bin", PROBE_SIZES[0][1])
        result.size_bytes = sum(f.stat().st_size for f in data_dir.rglob("*") if f.is_file())
        init = subprocess.run([restic_bin, "init"], env=env, capture_output=True, text=True)
        if init.returncode != 0 and "already exists" not in (init.stderr or "").lower():
            raise RuntimeError(init.stderr.strip() or f"restic init exit {init.returncode}")
        result.setup_ms = int((time.perf_counter() - setup_start) * 1000)
        result.setup_ok = True
        transfer_log.append(
            "protocol_setup_ok",
            run_id=run_id,
            source_id=SOURCE_ID,
            protocol=protocol,
            package_path=str(data_dir),
            repository=str(repo_dir),
            package_size_bytes=result.size_bytes,
            setup_ms=result.setup_ms,
        )
    except Exception as exc:
        result.error_message = str(exc)
        return finish_result(transfer_log, run_id, result, f"{run_id}:{protocol}")

    transfer_id = log_transfer_started(
        transfer_log,
        run_id,
        protocol,
        source=str(data_dir),
        destination=str(repo_dir),
        size_bytes=result.size_bytes,
    )
    try:
        start = time.perf_counter()
        proc = subprocess.run(
            [restic_bin, "backup", str(data_dir), "--json"],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        result.duration_ms = int((time.perf_counter() - start) * 1000)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or f"restic backup exit {proc.returncode}")
        verify_start = time.perf_counter()
        check = subprocess.run(
            [restic_bin, "check", "--read-data-subset", "1%"],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        result.verify_ms = int((time.perf_counter() - verify_start) * 1000)
        if check.returncode != 0:
            raise RuntimeError(check.stderr.strip() or "restic check failed")
        result.transfer_ok = True
        result.throughput_mib_s = performance_fields(result.size_bytes, result.duration_ms / 1000.0)[
            "throughput_mib_s"
        ]
        result.details["snapshot_lines"] = len([ln for ln in (proc.stdout or "").splitlines() if ln.strip()])
    except Exception as exc:
        result.error_message = str(exc)
    return finish_result(
        transfer_log, run_id, result, transfer_id, source=str(data_dir), destination=str(repo_dir)
    )


def _run_cmd(cmd: list[str], cwd: Path | None = None, timeout: int = 600) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def probe_nfs_smoke(_root: Path, transfer_log: TransferLog, run_id: str) -> ProtocolResult:
    protocol = "nfs_smoke"
    result = ProtocolResult(protocol=protocol, setup_ok=False, transfer_ok=False)
    repo = SILVER_FIESTA_REPO
    compose = repo / "scripts" / "container-compose.sh"
    if not repo.is_dir():
        result.skipped = True
        result.skip_reason = f"silver-fiesta repo not found at {repo}"
        return finish_result(transfer_log, run_id, result, f"{run_id}:{protocol}")

    log_probe_start(transfer_log, run_id, protocol)
    setup_start = time.perf_counter()
    try:
        if not compose.is_file():
            raise FileNotFoundError(f"missing {compose}")
        cfg = _run_cmd(["sh", str(compose), "config", "-q"], cwd=repo, timeout=120)
        if cfg.returncode != 0:
            raise RuntimeError(cfg.stderr.strip() or "compose config failed")
        venv_python = repo / ".venv" / "bin" / "python"
        pytest_cmd = [str(venv_python), "-m", "pytest", "tests/", "--collect-only", "-q"]
        if not venv_python.is_file():
            pytest_cmd = ["python3", "-m", "pytest", "tests/", "--collect-only", "-q"]
        collect = _run_cmd(pytest_cmd, cwd=repo, timeout=120)
        if collect.returncode != 0:
            raise RuntimeError(collect.stderr.strip() or "pytest collect failed")
        count_line = [ln for ln in collect.stdout.splitlines() if "test" in ln.lower()][-1:]
        result.setup_ok = True
        result.transfer_ok = True
        result.setup_ms = int((time.perf_counter() - setup_start) * 1000)
        result.duration_ms = result.setup_ms
        result.details["silver_fiesta_repo"] = str(repo)
        result.details["pytest_collect_tail"] = (count_line or [collect.stdout.strip().splitlines()[-1]])[0]
        transfer_log.append(
            "protocol_setup_ok",
            run_id=run_id,
            source_id=SOURCE_ID,
            protocol=protocol,
            silver_fiesta_repo=str(repo),
            setup_ms=result.setup_ms,
        )
    except Exception as exc:
        result.error_message = str(exc)
        return finish_result(transfer_log, run_id, result, f"{run_id}:{protocol}")

    transfer_id = log_transfer_started(transfer_log, run_id, protocol, destination=str(repo))
    return finish_result(transfer_log, run_id, result, transfer_id, destination=str(repo))


def probe_nfs_full(_root: Path, transfer_log: TransferLog, run_id: str) -> ProtocolResult:
    protocol = "nfs_full"
    result = ProtocolResult(protocol=protocol, setup_ok=False, transfer_ok=False)
    repo = SILVER_FIESTA_REPO
    makefile = repo / "Makefile"
    if not repo.is_dir() or not makefile.is_file():
        result.skipped = True
        result.skip_reason = f"silver-fiesta repo not found at {repo}"
        return finish_result(transfer_log, run_id, result, f"{run_id}:{protocol}")

    log_probe_start(transfer_log, run_id, protocol)
    transfer_id = log_transfer_started(transfer_log, run_id, protocol, destination=str(repo))
    start = time.perf_counter()
    try:
        proc = _run_cmd(["make", "test-lightweight"], cwd=repo, timeout=1800)
        result.duration_ms = int((time.perf_counter() - start) * 1000)
        result.setup_ok = True
        result.transfer_ok = proc.returncode == 0
        if not result.transfer_ok:
            tail = (proc.stdout or "")[-4000:] + (proc.stderr or "")[-4000:]
            result.error_message = tail.strip()[-500:] or f"make test-lightweight exit {proc.returncode}"
        else:
            result.details["reports_dir"] = str(repo / "tests" / "reports")
    except subprocess.TimeoutExpired:
        result.error_message = "silver-fiesta make test timed out (1800s)"
    except Exception as exc:
        result.error_message = str(exc)
    return finish_result(transfer_log, run_id, result, transfer_id, destination=str(repo))


ALL_PROBES: dict[str, ProbeFn] = {
    "local_chunked": probe_local_chunked,
    "local_rsync": probe_local_rsync,
    "rclone_smoke": probe_rclone_smoke,
    "rclone": probe_rclone,
    "restic_smoke": probe_restic_smoke,
    "restic": probe_restic,
    "nfs_smoke": probe_nfs_smoke,
    "nfs_full": probe_nfs_full,
}


def resolve_protocols(args: argparse.Namespace) -> list[str]:
    if args.doctor:
        names = list(DOCTOR_PROTOCOLS)
        if args.nfs_full:
            names.append("nfs_full")
        return names
    if args.protocol == "auto":
        names = ["local_chunked", "local_rsync", "rclone_smoke", "rclone", "restic_smoke", "restic"]
        if args.nfs_smoke:
            names.append("nfs_smoke")
        if args.nfs_full:
            names.append("nfs_full")
        return names
    names = [p.strip() for p in args.protocol.split(",") if p.strip()]
    if args.nfs_smoke and "nfs_smoke" not in names:
        names.append("nfs_smoke")
    if args.nfs_full and "nfs_full" not in names:
        names.append("nfs_full")
    return names


def render_human_table(results: list[ProtocolResult], log_path: Path, root: Path) -> None:
    table = Table(title="Silver Fiesta — transfer protocol validation", box=box.ROUNDED)
    table.add_column("Protocol", style="cyan")
    table.add_column("Setup", justify="center")
    table.add_column("Transfer", justify="center")
    table.add_column("MiB/s", justify="right")
    table.add_column("Duration", justify="right")
    table.add_column("Notes")

    for r in results:
        if r.skipped:
            table.add_row(r.protocol, "—", "—", "—", "—", f"skipped: {r.skip_reason}")
            continue
        setup = "[green]ok[/]" if r.setup_ok else "[red]fail[/]"
        xfer = "[green]ok[/]" if r.transfer_ok else "[red]fail[/]"
        mib = f"{r.throughput_mib_s:.2f}" if r.throughput_mib_s else "—"
        dur = f"{r.duration_ms}ms" if r.duration_ms else "—"
        note = r.error_message[:60] if r.error_message else "verified"
        table.add_row(r.protocol, setup, xfer, mib, dur, note)

    passed = sum(1 for r in results if r.ok)
    failed = [r for r in results if not r.skipped and not r.ok]
    skipped = sum(1 for r in results if r.skipped)
    summary = (
        f"Passed {passed}/{len(results)} probes "
        f"({skipped} skipped, {len(failed)} failed)\n"
        f"Workspace: {root}\n"
        f"Transfer log: {log_path}\n"
        f"Troubleshoot: grep transfer_failed {log_path} ; grep '^EBK' (with EBK_AI_STATUS=1)"
    )
    console.print(Panel(table, subtitle=summary))


def emit_json_summary(results: list[ProtocolResult], log_path: Path, root: Path, run_id: str) -> None:
    payload = {
        "run_id": run_id,
        "workspace": str(root),
        "transfer_log": str(log_path),
        "error_source": ERROR_SOURCE,
        "protocols": [
            {
                "protocol": r.protocol,
                "ok": r.ok,
                "skipped": r.skipped,
                "skip_reason": r.skip_reason,
                "setup_ok": r.setup_ok,
                "transfer_ok": r.transfer_ok,
                "error_message": r.error_message,
                "size_bytes": r.size_bytes,
                "setup_ms": r.setup_ms,
                "duration_ms": r.duration_ms,
                "verify_ms": r.verify_ms,
                "throughput_mib_s": r.throughput_mib_s,
                "sha256": r.sha256,
                "details": r.details,
            }
            for r in results
        ],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


def emit_ai_summary(results: list[ProtocolResult], log_path: Path, root: Path, run_id: str) -> None:
    for r in results:
        emit_ai_status(
            "protocol_row",
            source_id=SOURCE_ID,
            run_id=run_id,
            protocol=r.protocol,
            ok=r.ok,
            skipped=r.skipped,
            setup_ok=r.setup_ok,
            transfer_ok=r.transfer_ok,
            throughput_mib_s=r.throughput_mib_s,
            duration_ms=r.duration_ms,
            error_message=r.error_message or None,
        )
    passed = sum(1 for r in results if r.ok)
    emit_ai_status(
        "protocol_summary",
        source_id=SOURCE_ID,
        run_id=run_id,
        workspace=str(root),
        transfer_log=str(log_path),
        passed=passed,
        total=len(results),
        failed=len([r for r in results if not r.skipped and not r.ok]),
        skipped=sum(1 for r in results if r.skipped),
        status="ok" if passed == len(results) - sum(1 for r in results if r.skipped) else "degraded",
    )


def write_doctor_report(
    report_dir: Path,
    results: list[ProtocolResult],
    log_path: Path,
    root: Path,
    run_id: str,
) -> Path:
    """Persist triage artifacts for post-incident review (doctor / protocol-doctor.sh)."""
    report_dir.mkdir(parents=True, exist_ok=True)
    summary_path = report_dir / "summary.json"
    payload = {
        "tool": ERROR_SOURCE,
        "mode": "doctor",
        "run_id": run_id,
        "workspace": str(root),
        "transfer_log": str(log_path),
        "silver_fiesta_repo": str(SILVER_FIESTA_REPO),
        "protocols": [
            {
                "protocol": r.protocol,
                "ok": r.ok,
                "skipped": r.skipped,
                "skip_reason": r.skip_reason,
                "setup_ok": r.setup_ok,
                "transfer_ok": r.transfer_ok,
                "error_message": r.error_message,
                "throughput_mib_s": r.throughput_mib_s,
                "duration_ms": r.duration_ms,
                "details": r.details,
            }
            for r in results
        ],
    }
    summary_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    if log_path.is_file():
        shutil.copy2(log_path, report_dir / "transfer-log.jsonl")
    manifest = root / "MANIFEST.json"
    if manifest.is_file():
        shutil.copy2(manifest, report_dir / "MANIFEST.json")
    readme = report_dir / "README.txt"
    readme.write_text(
        "Silver Fiesta doctor report\n"
        f"run_id={run_id}\n"
        f"transfer_log={log_path}\n"
        "grep transfer_failed transfer-log.jsonl\n"
        "jq . summary.json\n",
        encoding="utf-8",
    )
    return summary_path


def write_manifest(root: Path, results: list[ProtocolResult], log_path: Path, run_id: str) -> Path:
    manifest = {
        "tool": ERROR_SOURCE,
        "run_id": run_id,
        "workspace": str(root),
        "transfer_log": str(log_path),
        "protocols": [
            {
                "protocol": r.protocol,
                "ok": r.ok,
                "skipped": r.skipped,
                "setup_ok": r.setup_ok,
                "transfer_ok": r.transfer_ok,
                "throughput_mib_s": r.throughput_mib_s,
                "duration_ms": r.duration_ms,
                "error_message": r.error_message,
            }
            for r in results
        ],
    }
    path = root / "MANIFEST.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    prepare_root(root, args.reuse)
    run_id = uuid4().hex[:12]
    log_path = args.log_path.resolve() if args.log_path else (root / "client" / TRANSFER_LOG_NAME)
    transfer_log = TransferLog(log_path)

    transfer_log.append(
        "package_created",
        run_id=run_id,
        source_id=SOURCE_ID,
        package_name="protocol-probe-bundle",
        package_path=str(root / "payloads"),
        package_size_bytes=0,
        package_sha256="",
        tool=ERROR_SOURCE,
    )
    log_event(
        logger,
        logging.INFO,
        "silver fiesta validation started",
        event_type="protocol_validation_started",
        command="validate",
        source_id=SOURCE_ID,
        details={"workspace": str(root), "run_id": run_id},
    )
    emit_ai_status("validate", source_id=SOURCE_ID, status="started", workspace=str(root), run_id=run_id)

    protocols = resolve_protocols(args)
    unknown = [p for p in protocols if p not in ALL_PROBES]
    if unknown:
        console.print(f"[red]Unknown protocol(s): {', '.join(unknown)}[/]")
        return 2

    results: list[ProtocolResult] = []
    for name in protocols:
        if args.format == "human":
            console.print(f"\n[bold]Probe {name}[/]")
        probe = ALL_PROBES[name]
        if args.fail_protocol == name:
            result = ProtocolResult(
                protocol=name,
                setup_ok=True,
                transfer_ok=False,
                error_message="simulated failure (--fail-protocol)",
            )
            log_probe_start(transfer_log, run_id, name)
            finish_result(transfer_log, run_id, result, f"{run_id}:{name}")
        else:
            result = probe(root, transfer_log, run_id)
        results.append(result)
        if args.format == "human":
            if result.skipped:
                console.print(f"  [yellow]skipped[/]: {result.skip_reason}")
            elif result.ok:
                console.print(
                    f"  [green]ok[/]  {result.duration_ms}ms"
                    + (f"  {result.throughput_mib_s:.2f} MiB/s" if result.throughput_mib_s else "")
                )
            else:
                console.print(f"  [red]fail[/]: {result.error_message}")

    transfer_log.append(
        "protocol_validation_completed",
        run_id=run_id,
        source_id=SOURCE_ID,
        passed=sum(1 for r in results if r.ok),
        failed=len([r for r in results if not r.skipped and not r.ok]),
        skipped=sum(1 for r in results if r.skipped),
        protocols=[r.protocol for r in results],
    )
    manifest_path = write_manifest(root, results, log_path, run_id)

    required = [p.strip() for p in args.require.split(",") if p.strip()]
    missing_required = []
    for name in required:
        match = next((r for r in results if r.protocol == name), None)
        if match is None:
            missing_required.append(f"{name}:unknown")
        elif match.skipped:
            missing_required.append(f"{name}:skipped ({match.skip_reason})")

    if args.report_dir:
        report_path = write_doctor_report(args.report_dir, results, log_path, root, run_id)
        if args.format == "human":
            console.print(f"Doctor report: {report_path.parent}/")

    if args.format == "json":
        emit_json_summary(results, log_path, root, run_id)
    elif args.format == "ai":
        emit_ai_summary(results, log_path, root, run_id)
    else:
        render_human_table(results, log_path, root)
        console.print(f"Manifest: {manifest_path}")

    if missing_required:
        msg = "Required protocols not satisfied: " + "; ".join(missing_required)
        if args.format == "human":
            console.print(f"[red]{msg}[/]")
        else:
            print(msg, file=sys.stderr)
        return 2

    required_failures = [r for r in results if not r.skipped and not r.ok]
    if required_failures:
        if args.format == "human":
            console.print(
                "\n[red]Protocol validation failed.[/] "
                "Use the transfer log and EBK lines to debug backup transfers:\n"
                f"  EBK_LOG_FORMAT=json EBK_AI_STATUS=1 python3 scripts/silver-fiesta.py --format ai\n"
                f"  grep transfer_failed {log_path}"
            )
        else:
            print(
                f"Protocol validation failed ({len(required_failures)} probe(s)). "
                f"transfer_log={log_path}",
                file=sys.stderr,
            )
        return 1
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nInterrupted", file=sys.stderr)
        sys.exit(130)
