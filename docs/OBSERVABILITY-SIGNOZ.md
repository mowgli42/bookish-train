# Observability and AI Terminal Integration

Edge Backup emits **structured JSON logs** and optional **OpenTelemetry** traces/logs for [SigNoz](https://signoz.io), plus **machine-readable status lines** for AI-native terminals such as [Chaterm](https://chaterm.ai) and OpenClaw-style agents.

## Design goals

1. **Agents can operate backups from the terminal** using stable text commands and parseable status output.
2. **Operators can correlate failures** in SigNoz using `service.name`, `trace_id`, and railway vocabulary (`source_id`, `package_id`, `event_type`).
3. **No silent degradation**: if OTLP libraries are missing, JSON logging still works.
4. **Failures name their source**: use `error_source` (component) and `operation` (step) on every error log.

## Sample logs for AI agents

Checked-in examples agents can read without running the stack:

| File | Description |
|------|-------------|
| `docs/samples/agent-logs-sample.jsonl` | Representative JSON log lines |
| `docs/samples/agent-ebk-sample.txt` | Representative `EBK` status lines |
| `docs/samples/agent-log-guide.md` | Parsing notes |

Regenerate after changing log shape:

```bash
python scripts/demo-observability.py --write-samples
```

Run the interactive demo (prints to terminal):

```bash
python scripts/demo-observability.py
```

### Failure fields agents should use

| Field | Example | Meaning |
|-------|---------|---------|
| `error_source` | `home-backup-chain-demo` | Which component failed |
| `operation` | `copy_hop:google-drive` | What step was running |
| `error_message` | `checksum mismatch ...` | Human-readable cause |
| `event_type` | `transfer_failed` | Railway / ledger vocabulary |

## Structured logging (always on)

Set:

```bash
export EBK_LOG_FORMAT=json          # default
export LOG_LEVEL=INFO
export OTEL_SERVICE_NAME=edge-backup-client
export DEPLOYMENT_ENV=home-lab
```

Logs are one JSON object per line on stderr, with fields aligned to SigNoz log search:

| Field | Purpose |
|-------|---------|
| `service.name` | Service identity in SigNoz |
| `severity` / `severity_text` | Log level |
| `body` / `message` | Human-readable text |
| `event_type` | Railway/ledger vocabulary |
| `source_id`, `package_id`, `path` | Backup context |
| `trace_id`, `span_id` | Present when OTLP tracing is active |

Implementation: `clients/common/edge_observability.py`.

## SigNoz / OpenTelemetry (optional)

Install exporters:

```bash
pip install -r scripts/requirements-observability.txt
```

Configure OTLP (SigNoz Cloud or self-hosted):

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT=https://ingest.<region>.signoz.cloud:443
# SigNoz Cloud often requires:
# export OTEL_EXPORTER_OTLP_HEADERS=signoz-ingestion-key=<your-key>
export OTEL_SERVICE_NAME=edge-backup-catcher
```

Local collector overlay:

```bash
docker compose -f docker-compose.yml -f docker-compose.observability.yml --profile observability up -d
```

### SigNoz best practices used here

- **Structured JSON logs** instead of unstructured `print()` for operational events.
- **Consistent resource attributes**: `service.name`, `service.version`, `deployment.environment`.
- **Correlate traces and logs** via OpenTelemetry SDK when installed.
- **Stable field names** for dashboards and alerts (`event_type=transfer_failed`, `status=failed`).
- **Do not log secrets**: paths in AI lines may be redacted by policy; full paths stay in dispatcher journal with access controls per OpenSpec home-safety rules.

## AI terminal status lines (EBK)

When `EBK_AI_STATUS=1`, components emit single-line records prefixed with `EBK`:

```
EBK	command=upload	status=completed	source_id=docker-client	path=photos/a.jpg	job_id=job-3	progress_percent=100
```

Agents can `grep '^EBK'` or split on tabs. JSON mode is available via `backup-agent.py --format json`.

Environment:

| Variable | Default | Meaning |
|----------|---------|---------|
| `EBK_AI_STATUS` | `1` | Emit EBK lines |
| `EBK_AI_STATUS_STREAM` | `stdout` | `stdout` or `stderr` |
| `EBK_OUTPUT_FORMAT` | `human` | Default format for `backup-agent.py` |

## Backup agent CLI (Chaterm / automation)

```bash
# Discover commands (paste into an AI terminal session)
python scripts/backup-agent.py commands --format ai

# Machine-readable dispatcher status
CATCHER_URL=http://127.0.0.1:8000 python scripts/backup-agent.py status --format ai

# List unfinished work for resume
python scripts/backup-agent.py resume --source-id my-laptop --format ai

# Tail yard ledger
python scripts/backup-agent.py journal --limit 10 --format json
```

Text UI also supports agent output:

```bash
python scripts/text-ui.py --format ai
python scripts/text-ui.py --format json
```

## Client engine integration

`clients/docker-client/watch_and_ingest.py` logs upload lifecycle events and emits EBK lines on state transitions when `EBK_AI_STATUS=1`.

## Dispatcher integration

`backend/main.py` logs ingest, patch, journal, and resume events with structured fields. Journal API remains the source of truth for audit; logs are for live operations and SigNoz alerts.

## Suggested SigNoz alerts

- `event_type = transfer_failed` rate &gt; 0 over 5m
- `status = failed` on client service without subsequent `status = completed`
- No `client_registered` or ingest activity from a known `source_id` in 24h (staleness)
