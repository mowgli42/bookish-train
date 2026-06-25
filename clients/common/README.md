# Edge Backup Common

Shared library for edge backup engines and external guardians (e.g. SnarkSentinel).

## Modules

| Module | Purpose |
|--------|---------|
| `client_interface.py` | `EdgeClientProtocol`, config/record models, compliance checks |
| `edge_observability.py` | Structured JSON logs, EBK AI status lines, status listeners |
| `transfer_log.py` | Append-only transfer audit log with query helpers |
| `agent_context.py` | Structured context export for AI agents |

## Usage

### PYTHONPATH (Docker clients, scripts)

```bash
export PYTHONPATH="/path/to/bookish-train/clients/common:${PYTHONPATH}"
python -c "from transfer_log import TransferLog; print(TransferLog)"
```

Docker clients add `clients/common` to `sys.path` automatically (see `watch_and_ingest.py`).

### Editable install

```bash
pip install -e clients/common
```

### SnarkSentinel integration

```bash
export EBK_COMMON_PATH=/path/to/bookish-train/clients/common
```

SnarkSentinel's `BackupGuardian` can load this package for shared EBK/transfer-log behavior.

### Guardian log tapping

```python
from edge_observability import register_status_listener, emit_ai_status

def on_status(command, fields):
    print("tapped", command, fields)

register_status_listener(on_status)
emit_ai_status("backup", source_id="my-laptop", status="started")
```

### Agent context export

```python
from pathlib import Path
from transfer_log import TransferLog
from agent_context import export_agent_context

log = TransferLog(Path("/var/log/edge-backup/transfer-log.jsonl"))
ctx = export_agent_context(log, source_id="my-laptop")
```
