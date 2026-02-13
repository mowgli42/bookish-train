# Beads task tracker

This project uses [Beads](https://steveyegge.github.io/beads/) for dependency-aware task tracking and AI session memory.

- **Initialize and seed tasks:** run `./scripts/beads-setup.sh` from the repo root (requires `bd` installed).
- **See unblocked work:** `bd ready`
- **List all open:** `bd list --status open`
- **Sync to git:** `bd sync`

The SQLite DB (`.beads/beads.db`) is gitignored; the JSONL store is git-tracked after `bd init`.
