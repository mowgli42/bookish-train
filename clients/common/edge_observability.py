"""
Structured logging and optional OpenTelemetry export for SigNoz.

Best practices applied:
- JSON structured logs with stable field names (service.name, severity, trace_id)
- Optional OTLP export when OTEL_EXPORTER_OTLP_ENDPOINT is set
- Machine-readable EBK status lines for AI terminals (Chaterm / OpenClaw agents)
- No print() for operational events; use get_logger() instead
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from collections.abc import Callable
from typing import Any

SERVICE_NAME = os.environ.get("OTEL_SERVICE_NAME", "edge-backup")
SERVICE_VERSION = os.environ.get("OTEL_SERVICE_VERSION", "0.1.0")
DEPLOYMENT_ENV = os.environ.get("DEPLOYMENT_ENV", os.environ.get("EBK_ENV", "development"))
LOG_FORMAT = os.environ.get("EBK_LOG_FORMAT", "json").lower()
AI_STATUS_ENABLED = os.environ.get("EBK_AI_STATUS", "1").lower() in ("1", "true", "yes", "on")
AI_STATUS_STREAM = os.environ.get("EBK_AI_STATUS_STREAM", "stdout").lower()

_OTEL_READY = False
_CONFIGURED: set[str] = set()
_STATUS_LISTENERS: list[Callable[[str, dict[str, Any]], None]] = []


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ai_stream() -> Any:
    if AI_STATUS_STREAM == "stderr":
        return sys.stderr
    return sys.stdout


class StructuredFormatter(logging.Formatter):
    """SigNoz-friendly JSON log lines (one object per line)."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": _now_iso(),
            "severity": record.levelname,
            "severity_text": record.levelname,
            "body": record.getMessage(),
            "message": record.getMessage(),
            "logger": record.name,
            "service.name": getattr(record, "service_name", SERVICE_NAME),
            "service.version": SERVICE_VERSION,
            "deployment.environment": DEPLOYMENT_ENV,
        }
        for key, attr in (
            ("event_type", "event_type"),
            ("command", "command"),
            ("source_id", "source_id"),
            ("package_id", "package_id"),
            ("job_id", "job_id"),
            ("station_id", "station_id"),
            ("status", "status"),
            ("path", "path"),
            ("package_type", "package_type"),
            ("actor", "actor"),
            ("error_source", "error_source"),
            ("operation", "operation"),
            ("error_message", "error_message"),
            ("error_type", "error_type"),
        ):
            value = getattr(record, attr, None)
            if value is not None:
                payload[key] = value
        details = getattr(record, "details", None)
        if isinstance(details, dict) and details:
            payload["details"] = details
        trace_id = getattr(record, "trace_id", None)
        span_id = getattr(record, "span_id", None)
        if trace_id:
            payload["trace_id"] = trace_id
        if span_id:
            payload["span_id"] = span_id
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, separators=(",", ":"))


def _try_init_otel(service_name: str) -> None:
    global _OTEL_READY
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    if not endpoint or _OTEL_READY:
        return
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry._logs import set_logger_provider
        from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
        from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
        from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
    except ImportError:
        return

    resource = Resource.create(
        {
            "service.name": service_name,
            "service.version": SERVICE_VERSION,
            "deployment.environment": DEPLOYMENT_ENV,
        }
    )
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
    trace.set_tracer_provider(provider)

    log_provider = LoggerProvider(resource=resource)
    log_provider.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter(endpoint=endpoint)))
    set_logger_provider(log_provider)
    root = logging.getLogger()
    if not any(isinstance(h, LoggingHandler) for h in root.handlers):
        root.addHandler(LoggingHandler(level=logging.NOTSET, logger_provider=log_provider))

    _OTEL_READY = True


def configure_observability(service_name: str | None = None, level: int | None = None) -> logging.Logger:
    """Configure JSON logging (and optional OTLP) once per service name."""
    name = service_name or SERVICE_NAME
    if name in _CONFIGURED:
        return logging.getLogger(name)

    log_level = level
    if log_level is None:
        log_level = getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO)

    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler(sys.stderr)
        if LOG_FORMAT == "json":
            handler.setFormatter(StructuredFormatter())
        else:
            handler.setFormatter(
                logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
            )
        root.addHandler(handler)
    root.setLevel(log_level)

    _try_init_otel(name)
    _CONFIGURED.add(name)
    return logging.getLogger(name)


def get_logger(name: str | None = None) -> logging.Logger:
    configure_observability(SERVICE_NAME)
    return logging.getLogger(name or SERVICE_NAME)


def log_event(
    logger: logging.Logger,
    level: int,
    message: str,
    *,
    event_type: str,
    command: str | None = None,
    source_id: str | None = None,
    package_id: str | None = None,
    job_id: str | None = None,
    station_id: str | None = None,
    status: str | None = None,
    path: str | None = None,
    package_type: str | None = None,
    actor: str | None = None,
    details: dict | None = None,
) -> None:
    """Emit a structured operational log tied to backup vocabulary."""
    extra = {
        "event_type": event_type,
        "command": command,
        "source_id": source_id,
        "package_id": package_id or job_id,
        "job_id": job_id or package_id,
        "station_id": station_id,
        "status": status,
        "path": path,
        "package_type": package_type,
        "actor": actor,
        "details": details or {},
        "service_name": SERVICE_NAME,
    }
    logger.log(level, message, extra=extra)


def log_error(
    logger: logging.Logger,
    message: str,
    *,
    event_type: str,
    error_source: str,
    operation: str,
    error_message: str | None = None,
    exc: BaseException | None = None,
    command: str | None = None,
    source_id: str | None = None,
    package_id: str | None = None,
    job_id: str | None = None,
    station_id: str | None = None,
    path: str | None = None,
    details: dict | None = None,
) -> None:
    """Log a failure with explicit component and operation for agents and SigNoz."""
    err_text = error_message or message
    err_type = type(exc).__name__ if exc else "Error"
    merged_details = {
        "error_source": error_source,
        "operation": operation,
        "error_message": err_text,
        "error_type": err_type,
        **(details or {}),
    }
    extra = {
        "event_type": event_type,
        "command": command,
        "source_id": source_id,
        "package_id": package_id or job_id,
        "job_id": job_id or package_id,
        "station_id": station_id,
        "status": "failed",
        "path": path,
        "error_source": error_source,
        "operation": operation,
        "error_message": err_text,
        "error_type": err_type,
        "details": merged_details,
        "service_name": SERVICE_NAME,
    }
    if exc:
        logger.error(message, exc_info=exc, extra=extra)
    else:
        logger.error(message, extra=extra)
    emit_ai_status(
        "error",
        error_source=error_source,
        operation=operation,
        event_type=event_type,
        error_message=err_text,
        error_type=err_type,
        source_id=source_id,
        package_id=package_id or job_id,
        path=path,
        station_id=station_id,
    )


def _escape_ai_value(value: Any) -> str:
    text = str(value)
    if any(ch in text for ch in ("\t", "\n", "\r")):
        return json.dumps(text, ensure_ascii=False)
    return text


def format_ai_line(command: str, fields: dict[str, Any]) -> str:
    """Single-line status for AI terminals (Chaterm / OpenClaw). Prefix: EBK."""
    parts = [f"command={_escape_ai_value(command)}"]
    for key in sorted(fields):
        if fields[key] is None:
            continue
        parts.append(f"{key}={_escape_ai_value(fields[key])}")
    return "EBK\t" + "\t".join(parts)


def register_status_listener(listener: Callable[[str, dict[str, Any]], None]) -> None:
    """Register a callback for EBK status lines (e.g. SnarkSentinel log tapping)."""
    _STATUS_LISTENERS.append(listener)


def unregister_status_listener(listener: Callable[[str, dict[str, Any]], None]) -> None:
    _STATUS_LISTENERS[:] = [item for item in _STATUS_LISTENERS if item is not listener]


def emit_ai_status(command: str, **fields: Any) -> None:
    """Write a machine-readable status line agents can grep or parse."""
    fields.setdefault("timestamp", _now_iso())
    fields.setdefault("service", SERVICE_NAME)
    for listener in _STATUS_LISTENERS:
        listener(command, dict(fields))
    if not AI_STATUS_ENABLED:
        return
    line = format_ai_line(command, fields)
    print(line, file=_ai_stream(), flush=True)


def emit_ai_json(command: str, **fields: Any) -> None:
    """JSONL status event for agents that prefer JSON."""
    payload = {"type": "ebk_status", "command": command, "timestamp": _now_iso(), **fields}
    print(json.dumps(payload, default=str, separators=(",", ":")), file=_ai_stream(), flush=True)
