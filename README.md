# Edge Backup System

Treat edge devices as **cattle, not pets**: data does not reside on the edge. It is packaged, tracked, and stored in cloud or offsite storage. This repo implements an end-to-end data backup strategy with minimal tooling.

- **Edge clients:** Minimal scripts that watch folders, package data, and forward to a catcher.
- **Catcher service:** Receives ingest requests, tracks jobs and sources, and (in later phases) manages storage tiers (hot/warm/cold) and offsite.
- **Web dashboard:** Read-only UI to track transfer progress. Scripts do the transfers; the UI only displays status.

Development is **spec-driven** (OpenSpec) and **task-tracked** (Beads): one source-of-truth spec, phased tasks with dependencies, and a clear workflow for AI and humans.

---

## Project structure

```
bookish-train/
├── openspec/
│   └── specs/
│       └── edge-backup-system.md   # Single source of truth: architecture, API, models
├── .beads/                         # Beads task DB (after bd init); beads.db gitignored
├── scripts/
│   └── beads-setup.sh              # Seed Beads with phased tasks
├── backend/                        # Catcher (FastAPI)
│   ├── main.py
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                       # Dashboard (Svelte 5, minimal stores)
│   ├── src/
│   │   ├── App.svelte
│   │   ├── main.js
│   │   └── stores/
│   │       └── jobs.js
│   ├── package.json
│   ├── vite.config.js
│   └── Dockerfile
├── clients/
│   └── docker-client/              # Phase 1: container client (watch dir → POST /ingest)
│       ├── watch_and_ingest.py
│       ├── Dockerfile
│       └── test-data/
├── docker-compose.yml              # Phase 1: catcher + client + dashboard
├── tests/                          # Playwright E2E + visual capture
│   ├── e2e/
│   │   └── dashboard.spec.js
│   └── README.md
├── docs/
│   └── VALIDATION-WORKFLOW.md      # Validation workflow, commands, screenshots
├── AGENTS.md                       # How AI agents should use Beads and OpenSpec
└── README.md
```

---

## Running the app

### Option A: Local (no Docker)

**Backend**

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

**Frontend**

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The Vite dev server proxies `/api` to `http://localhost:8000`.

**Client (optional)**

```bash
# From repo root, with catcher and optional test dir
export CATCHER_URL=http://localhost:8000
export WATCH_DIR=./clients/docker-client/test-data
python clients/docker-client/watch_and_ingest.py
```

### Option B: Docker (Phase 1 prototype)

```bash
docker compose up --build
```

- Catcher: http://localhost:8000  
- Dashboard: http://localhost:5173  
- Client container watches `clients/docker-client/test-data` and POSTs to the catcher. Add files there to see jobs in the dashboard.

### Populate demo data (see dashboard with jobs)

With catcher and dashboard running:

```bash
python scripts/seed-demo-data.py
```

Then open http://localhost:5173 and click Refresh. Uses `tests/fixtures/mock-data/MANIFEST.json` (5 mock files). Optional: `--source my-source`, `--url http://other:8000`.

---

## OpenSpec (spec-driven development)

OpenSpec keeps a single source-of-truth spec so humans and AI agree on what to build before coding.

- **Spec file:** `openspec/specs/edge-backup-system.md` — architecture, phases, API endpoints, JSON data models, validation rules.
- **Workflow:** Propose changes in the spec → implement → update Beads when done.

**Install OpenSpec (npm)**

```bash
npm install -g @fission-ai/openspec@latest
cd /path/to/bookish-train
openspec init
```

Then use slash commands in your AI tool (e.g. Cursor): `/opsx:new <feature>`, `/opsx:ff`, `/opsx:apply`, `/opsx:archive`. Our spec is already in `openspec/specs/`; you can point changes at it or create new capability specs.

---

## Beads (progress tracker)

Beads is a git-backed, dependency-aware task tracker. Use it for session memory and to see what work is unblocked.

**Install Beads**

- **macOS / Linux:** `brew install beads` or [quick install script](https://raw.githubusercontent.com/steveyegge/beads/main/scripts/install.sh).
- **Go:** `go install github.com/steveyegge/beads/cmd/bd@latest`
- **Windows:** [PowerShell installer](https://raw.githubusercontent.com/steveyegge/beads/main/install.ps1) or `go install` (see [Beads installation](https://steveyegge.github.io/beads/getting-started/installation)).

**Initialize and seed tasks in this repo**

```bash
./scripts/beads-setup.sh
```

This runs `bd init` and creates phased tasks (Phase 1: backend, routes, frontend, Docker, client script; Phase 2: Windows agent and package; Phase 3/4 placeholders). Add dependencies between tasks with:

```bash
bd dep add <blocked-task-id> <blocker-task-id>
```

**Useful commands**

- **Unblocked work:** `bd ready`
- **List open:** `bd list --status open`
- **List closed (Phase 1 done):** `bd list --status closed`
- **Sync to git:** `bd sync`
- **Cursor integration:** `bd setup cursor` (injects workflow context)

**Seeing Beads updates:** Run `bd sync`, then `git add .beads/issues.jsonl .beads/config.yaml .beads/metadata.json` and commit. The JSONL is the source of truth; commit it to persist progress across sessions and share with collaborators.

For **AI agents:** see `AGENTS.md` for how to use Beads for session memory and task management.

---

## Phases (summary)

| Phase | Scope |
|-------|--------|
| **1** | Docker prototype: catcher API, Svelte dashboard, client container that watches a dir and POSTs to `/api/v1/ingest`. |
| **2** | MVP Windows endpoint: agent that monitors local folders and forwards to catcher; package for deployment. |
| **3** | Additional clients (Linux, macOS) and network filesystem sources. |
| **4** | Cloud storage tiers (hot/warm/cold) and offsite storage. |

Details and API/validation rules are in `openspec/specs/edge-backup-system.md`.

---

## Validation Tests (Playwright)

Per-phase E2E tests and workflow documentation:

```bash
# Start catcher + dashboard first, then:
npm install
npm run test:e2e
```

→ [docs/VALIDATION-WORKFLOW.md](docs/VALIDATION-WORKFLOW.md) — prerequisites, commands, workflow with screenshots.

**Progress:** Track tasks in [docs/TASKS.md](docs/TASKS.md) or run `./scripts/beads-setup.sh` when Beads is installed.
