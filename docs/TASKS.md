# Beads task manifest

Beads is the source of truth for progress. Run `bd ready` to see unblocked work.

**Workflow:** `bd ready` → pick task → implement → `bd close <id>` → `bd sync`

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

## Phase 2: MVP Windows

| ID | Task | Deps | Status |
|----|------|------|--------|
| P2-1 | Windows endpoint agent (monitor local folders) | P1-8 | ⬜ ready |
| P2-2 | Package Windows tooling for deployment | P2-1 | ⬜ |

## Phase 3 & 4

| ID | Task | Deps | Status |
|----|------|------|--------|
| P3-1 | Linux/macOS clients and network filesystems | P2-2 | ⬜ |
| P4-1 | Cloud storage tiers (hot/warm/cold) and offsite | P3-1 | ⬜ |

*Run `bd ready` for current unblocked tasks; `bd list` for all.*

**Seeing Beads updates:** Beads stores state in `.beads/issues.jsonl`. Run `bd sync`, then:
```bash
git add .beads/issues.jsonl .beads/config.yaml .beads/metadata.json
git commit -m "chore: update Beads task state"
```
Commit this file to persist progress and share across sessions. Without committing, updates stay local only.
