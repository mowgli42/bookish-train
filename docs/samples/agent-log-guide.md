# Agent log samples

Use these files to teach AI terminals (Chaterm, OpenClaw) and automation how Edge Backup logs look **before** connecting to a live dispatcher.

## Files

| File | Format | Use |
|------|--------|-----|
| `agent-logs-sample.jsonl` | One JSON object per line (stderr in production) | SigNoz, jq, grep |
| `agent-ebk-sample.txt` | `EBK` + tab-separated `key=value` | Terminal agents, `grep '^EBK'` |

## Regenerate

```bash
python scripts/demo-observability.py --write-samples
```

## Parsing JSON logs

Each line is a complete JSON object. Important fields:

- `event_type` — railway vocabulary (`manifest_created`, `transfer_failed`, `client_upload`, …)
- `severity` — `INFO`, `ERROR`, …
- `error_source` — component that failed (`home-backup-chain-demo`, `verify-engine`, `backup-agent`)
- `operation` — step that failed (`copy_hop`, `transfer_failed`, `status`)
- `error_message` — human-readable cause
- `source_id`, `package_id`, `path`, `station_id` — backup context

Example query:

```bash
grep '"event_type":"transfer_failed"' docs/samples/agent-logs-sample.jsonl
```

## Parsing EBK lines

Every line starts with `EBK`, then tab-separated fields like `command=upload`.

```bash
grep '^EBK' docs/samples/agent-ebk-sample.txt
grep 'error_source=' docs/samples/agent-ebk-sample.txt
```

## Live demos

```bash
python scripts/demo-observability.py          # print samples to terminal
python scripts/backup-agent.py status --format ai   # needs Catcher
```

See also [`docs/OBSERVABILITY-SIGNOZ.md`](../OBSERVABILITY-SIGNOZ.md) and README § AI terminals.
