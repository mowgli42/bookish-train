"""Backend observability shim — reuses clients/common edge_observability."""
from __future__ import annotations

import sys
from pathlib import Path

_COMMON = Path(__file__).resolve().parent.parent / "clients" / "common"
if str(_COMMON) not in sys.path:
    sys.path.insert(0, str(_COMMON))

from edge_observability import (  # noqa: E402
    configure_observability,
    emit_ai_status,
    log_event,
)

__all__ = ["configure_observability", "emit_ai_status", "log_event", "get_logger"]


def get_logger():
    return configure_observability("edge-backup-catcher")
