# Beads task tracker

This project uses [Beads](https://gastownhall.github.io/beads/) for dependency-aware task tracking and AI session memory.

- **Agent/dev environment:** run `./scripts/setup-agent-env.sh` from the repo root (installs `bd` from [gastownhall/beads](https://github.com/gastownhall/beads), puts `~/.local/bin` on `PATH` for the session, installs `backend/requirements.txt`, and skips `bd init` if `.beads/metadata.json` already exists).
- **Initialize and seed tasks:** run `./scripts/beads-setup.sh` from the repo root (requires `bd` installed).
- **See unblocked work:** `bd ready`
- **List all open:** `bd list --status open`
- **Export tracked state:** `bd export -o .beads/issues.jsonl`

The local Beads database is gitignored; the JSONL store is git-tracked after `bd init`/`bd bootstrap`.
