# Personal Computer Backup MVP Plan

This review turns the current prototype into an executable effort for people who want to run backups on personal computers.

## Current state

- The Catcher API, dashboard, text UI, and validation fixtures exist.
- `clients/docker-client/watch_and_ingest.py` is a minimal metadata-ingest watcher. It keeps seen files in memory and does not move backup payloads.
- `scripts/restic-rclone-backup.py` proves progress reporting for restic/rclone, but it is not a configured personal-computer client.
- `scripts/home-backup-chain-demo.py` proves the desired home-client to NAS to Google Drive to backup-service flow locally, including checksum verification, transfer log records, and resend from log.
- `docs/RAILWAY-ARCHITECTURE.md` defines the canonical train-and-rail vocabulary: engines move data; the dispatcher API tracks manifests, resume work, configuration snapshots, and the activity journal; the web dashboard is the signal board.

## Gap to first-user usability

A personal-computer user needs more than the demo:

1. A clear config file for watch folders, staging, local log, NAS, cloud/offsite destinations, and optional Catcher URL.
2. Durable queued work so restarts do not lose pending backups.
3. A reusable backup engine that is not tied to demo paths.
4. Real destination adapters: local/NAS first, then rclone remotes and restic repositories.
5. CLI commands for init, config validation, one-shot run, status, resend, and restore smoke test.
6. An end-to-end local validation scenario that proves the user workflow without requiring provider credentials.
7. A quick start and recovery runbook a non-developer can follow.
8. Dispatcher persistence for resume work, configuration/timetable snapshots, and append-only activity journal/yard ledger (optional SQLite via `CATCHER_SQLITE_PATH` or `DATABASE_URL=sqlite:///...`; see OpenSpec §1.1.3 and §4.10).
9. Ransomware-aware safety controls: panic brake, canary files, suspicious-change detection, immutable/offline history, and no automatic destructive sync.
10. Passkey or local unlock for sensitive dashboard/API actions so the Signal Board does not become a roadmap for attackers.

## Beads execution path

The executable effort is tracked under the Beads epic `workspace-0n4` (`Personal computer backup MVP`).

Run:

```bash
bd ready --json
```

The first unblocked implementation task is:

- `workspace-0n4.1` — define installable backup client scope and default flow.

After that, work fans out into:

- config schema/validation
- reusable backup-chain engine
- durable watcher/queue
- production transfer log and resend semantics
- local NAS/filesystem transport
- rclone and restic transports
- user-facing CLI
- end-to-end validation
- quick start and recovery docs
- dispatcher resume protocol
- configuration snapshots and activity journal
- ransomware panic brake and canary files
- passkey/local unlock for sensitive API and dashboard views
- restore drills and immutable/offline backup guidance

## Definition of usable

The MVP is usable when a person can:

1. Install prerequisites or run a packaged client.
2. Create a config for personal folders and destinations.
3. Run a backup.
4. Verify that all configured copies exist and match checksums.
5. See what was sent in a local log/status command.
6. Remove or corrupt a downstream copy and successfully resend it.
7. Restore at least one file and match its checksum.
8. Restart after a failed transfer and receive a dispatcher switch list for unfinished work.
9. Export/restore dispatcher configuration and activity journal records.
10. Detect likely ransomware behavior and stop normal backup movement before overwriting good recovery points.
11. Use a passkey/local unlock to reveal full paths, alter routes, resume after panic brake, or run destructive operations.
12. Prove photos/documents can be restored from both local/NAS and IDrive e2/restic recovery points.

## Home reliability and ransomware plan

See [`docs/HOME-RELIABILITY-RANSOMWARE.md`](HOME-RELIABILITY-RANSOMWARE.md) for the home-use safety strategy. The short version:

- keep the system home-focused and understandable
- use TrueNAS snapshots and IDrive e2/restic history for recovery points
- do not propagate deletes as immediate backup deletes
- pause backups when suspicious mass changes are detected
- require passkey/manual unlock for sensitive details and dangerous actions
- test restore regularly
