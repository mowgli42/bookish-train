# Beads task manifest

Beads is the source of truth for progress. Run `bd ready` to see unblocked work.

**Workflow:** `bd ready --json` → pick task → implement → `bd close <id>` → `bd export -o .beads/issues.jsonl`

**Seed (fresh repo):** `./scripts/beads-setup.sh`

---

## Phase 1: Prototype

| ID | Task | Deps | Status |
|----|------|------|--------|
| P1-1 | Init catcher backend (FastAPI) | — | ✅ done |
| P1-2 | Define API routes (ingest, jobs, sources) | P1-1 | ✅ done |
| P1-3 | Checksum required when size_bytes > 0 | P1-2 | ✅ done |
| P1-4 | Init frontend (Svelte) and dashboard | P1-1 | ✅ done |
| P1-5 | Dashboard: sources list view | P1-4 | ✅ done |
| P1-6 | Dashboard: IxDF signifiers and feedback | P1-5 | ✅ done |
| P1-7 | Docker Compose (catcher + client + dashboard) | P1-2, P1-4 | ✅ done |
| P1-8 | Client script in container (watch dir, POST /ingest) | P1-7 | ✅ done |
| P1-9 | Playwright validation (health, dashboard, sources) | P1-6, P1-7 | ✅ done |
| P1-10 | Fix Svelte \$state rune: stores must be .svelte.js | P1-6 | ✅ done |

### Text UI (P1 parallel)

| ID | Task | Deps | Status |
|----|------|------|--------|
| text-console-1a2 | Text UI — one-shot status report (component status, buckets) | — | ✅ done |
| text-console-2b3 | Text UI — packages, clients, rules, projections | — | ✅ done |
| text-console-3c4 | Text UI — live refresh mode (--live, CATCHER_URL) | text-console-1a2 | ✅ done |

See OpenSpec §1.5 for requirements. Script: `scripts/text-ui.py`; env: `CATCHER_URL`.

## Phase 2: MVP Windows

| ID | Task | Deps | Status |
|----|------|------|--------|
| P2-1 | Windows endpoint agent (monitor local folders) | P1-8, workspace-0n4.9 | ⬜ |
| P2-2 | Package Windows tooling for deployment | P2-1 | ⬜ |

## Personal computer backup MVP

The current executable effort is tracked by the `Personal computer backup MVP` Beads epic (`workspace-0n4`). Run `bd ready --json` for the next unblocked task.

| ID | Task | Deps | Status |
|----|------|------|--------|
| workspace-0n4.1 | Define installable backup client scope and default flow | — | ⬜ ready |
| workspace-0n4.2 | Configuration file schema and validation | workspace-0n4.1 | ⬜ |
| workspace-0n4.3 | Reusable backup-chain engine from demo flow | workspace-0n4.1 | ⬜ |
| workspace-0n4.4 | Watch folders and queue changed files safely | workspace-0n4.2, workspace-0n4.3 | ⬜ |
| workspace-0n4.5 | Production transfer log and resend semantics | workspace-0n4.3 | ⬜ |
| workspace-0n4.6 | Local NAS/filesystem destination | workspace-0n4.2, workspace-0n4.3 | ⬜ |
| workspace-0n4.7 | rclone destinations for Google Drive and backup services | workspace-0n4.2, workspace-0n4.3 | ⬜ |
| workspace-0n4.8 | restic repository backup and restore smoke test | workspace-0n4.2, workspace-0n4.3 | ⬜ |
| workspace-0n4.9 | CLI: init, run, status, resend, restore | workspace-0n4.4, workspace-0n4.5, workspace-0n4.6 | ⬜ |
| workspace-0n4.10 | End-to-end personal-computer backup scenario | workspace-0n4.7, workspace-0n4.8, workspace-0n4.9 | ⬜ |
| workspace-0n4.11 | Personal backup quick start and recovery runbook | workspace-0n4.10 | ⬜ |

## Phase 3 & 4

| ID | Task | Deps | Status |
|----|------|------|--------|
| P3-1 | Linux/macOS clients and network filesystems | P2-2 | ⬜ |
| P4-1 | Cloud storage tiers (hot/warm/cold) and offsite | P3-1 | ⬜ |

### Demo artifacts

| ID | Task | Deps | Status |
|----|------|------|--------|
| DEMO-1 | Local provider-chain demo: home client → local NAS → Google Drive → backup service | — | ✅ done |
| DEMO-2 | Local client transfer log for sent-data audit and resend | DEMO-1 | ✅ done |

*Run `bd ready` for current unblocked tasks; `bd list` for all.*

**Seeing Beads updates:** Beads stores tracked state in `.beads/issues.jsonl`. Run `bd export -o .beads/issues.jsonl`, then:
```bash
git add .beads/issues.jsonl .beads/config.yaml .beads/metadata.json
git commit -m "chore: update Beads task state"
```
Commit this file to persist progress and share across sessions. Without committing, updates stay local only.
