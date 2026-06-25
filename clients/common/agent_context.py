"""
Structured context export for AI agents and external guardians (SnarkSentinel, OpenClaw).

Provides machine-readable bundles from transfer logs and EBK status without
requiring agents to scrape raw log files.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from transfer_log import TransferLog


def export_agent_context(
    transfer_log: TransferLog,
    *,
    source_id: str,
    recent_limit: int = 20,
) -> dict[str, Any]:
    """Build a context document suitable for agent/MCP consumption."""
    recent = transfer_log.recent(limit=recent_limit)
    latest = transfer_log.latest_package()
    failures = transfer_log.failed_transfers(source_id=source_id)
    return {
        "type": "ebk_agent_context",
        "version": "1",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source_id": source_id,
        "transfer_log_path": str(transfer_log.path),
        "summary": {
            "recent_count": len(recent),
            "failed_count": len(failures),
            "latest_package_path": latest.get("path") if latest else None,
            "healthy": bool(latest) and not failures,
        },
        "latest_package": latest,
        "failed_transfers": failures,
        "recent_transfers": recent,
    }


def format_agent_context_json(
    transfer_log: TransferLog,
    *,
    source_id: str,
    recent_limit: int = 20,
) -> str:
    """JSON string for piping to agents or writing to a review bundle."""
    import json

    return json.dumps(
        export_agent_context(transfer_log, source_id=source_id, recent_limit=recent_limit),
        indent=2,
        sort_keys=True,
        default=str,
    )
