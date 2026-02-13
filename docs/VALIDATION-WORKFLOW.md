# Validation Workflow

Per-phase validation tests using Playwright. Tests capture web displays and document the workflow for each phase and tool in the toolbox.

---

## Prerequisites

1. **Catcher** running on `http://localhost:8000`
2. **Dashboard** running on `http://localhost:5173`
3. **(Optional)** Client container or script running to produce ingest jobs

---

## Quick Start

**Option A – Servers already running** (e.g. you started them manually):
```bash
npm run test:e2e
```

**Option B – One command** (Playwright will start backend + frontend if needed):
```bash
npm install
npm run test:e2e
```
The config starts backend (8000) and frontend (5173) when they’re not running. Uses `127.0.0.1` to avoid IPv6 issues.

**Option C – Start servers separately** (e.g. for debugging):
```bash
npm run serve   # backend + frontend in one terminal
# In another terminal:
npm run test:e2e
```

---

## Mock Data

Mock files for transfer validation live in `tests/fixtures/mock-data/`:

| File | Size | Purpose |
|------|------|---------|
| sample.txt | 6 B | Plain text |
| report.json | 24 B | JSON |
| data/backup-001.log | 80 B | Nested path |
| empty.bin | 0 B | Zero-byte |
| config.ini | 38 B | Config-style |

Checksums and tier hints are in `tests/fixtures/mock-data/MANIFEST.json`.

**Seed script (quickest):**
```bash
python scripts/seed-demo-data.py
```
Then open the dashboard and click Refresh.

**Alternatively:** Point `WATCH_DIR` at `tests/fixtures/mock-data` for the client, or POST payloads from the manifest to `/api/v1/ingest`.

---

## Workflow Captured (Phase 1)

| Step | Action | Screenshot / Artifact |
|------|--------|------------------------|
| 1 | Start catcher + dashboard | — |
| 2 | Open dashboard | `dashboard-empty.png` |
| 3 | Click Refresh | Jobs list (empty or populated) |
| 4 | Seed mock data: `WATCH_DIR=tests/fixtures/mock-data` or POST from MANIFEST.json | Client ingests; jobs appear |
| 5 | Refresh again | `dashboard-with-jobs.png` |

---

## Commands

| Command | Purpose |
|---------|---------|
| `npm run test:e2e` | Run full Playwright suite |
| `npm run test:e2e:ui` | Interactive Playwright UI mode |
| `npm run test:e2e:update` | Update baseline snapshots after intentional UI changes |

---

## Baseline Snapshots

Snapshots live in `tests/e2e/snapshots/`. On first run, Playwright creates baselines. Subsequent runs compare against them.

**To update baselines** (e.g. after a deliberate design change):

```bash
npm run test:e2e:update
```

---

## Per-Phase Test Matrix

| Phase | Tests | Captures |
|-------|-------|----------|
| **1** (Prototype) | Health, ingest, jobs, sources | Dashboard empty; dashboard with jobs |
| **2** (MVP) | Windows client ingest | Same + Windows agent status (if UI) |
| **3** (Extend) | Per-client type (Linux, macOS, NFS) | Multi-source dashboard |
| **4** (Storage) | Tier transitions, retention | Tier labels, retention config UI |

---

## Environment

- **BASE_URL:** Override dashboard URL (default `http://localhost:5173`)

  ```bash
  BASE_URL=http://localhost:3000 npm run test:e2e
  ```

- **CATCHER_URL:** Override catcher URL for API requests (default `http://localhost:8000`). Needed when `dashboard-with-jobs` test runs against a different backend.

  ```bash
  CATCHER_URL=http://catcher:8000 npm run test:e2e
  ```

---

## CI Integration

Playwright can run in CI. Ensure catcher and dashboard are started (e.g. via Docker Compose or npm scripts) before `npm run test:e2e`.
