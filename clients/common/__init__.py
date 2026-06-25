"""Shared client and service utilities for edge backup engines."""

from client_interface import (
    ClientConfig,
    EdgeClientProtocol,
    PackageRecord,
    PackageStatus,
    StatusUpdate,
    TransferRecord,
    TransferStatus,
    client_interface_checks,
)
from edge_observability import (
    configure_observability,
    emit_ai_status,
    format_ai_line,
    get_logger,
    log_error,
    log_event,
    register_status_listener,
    unregister_status_listener,
)
from transfer_log import TransferLog, performance_fields, sha256_file

__all__ = [
    "ClientConfig",
    "EdgeClientProtocol",
    "PackageRecord",
    "PackageStatus",
    "StatusUpdate",
    "TransferRecord",
    "TransferStatus",
    "TransferLog",
    "client_interface_checks",
    "configure_observability",
    "emit_ai_status",
    "format_ai_line",
    "get_logger",
    "log_error",
    "log_event",
    "performance_fields",
    "register_status_listener",
    "sha256_file",
    "unregister_status_listener",
]
