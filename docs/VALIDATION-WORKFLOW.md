# Phase 1 Validation Workflow

How to run Phase 1 assessment: containers (Podman or Docker), individual tools, scenario script, and Playwright e2e.

## Prerequisites

- **Podman** (preferred) or **Docker** — for containerized assessment. Scripts auto-detect; set `CONTAINER_RUNTIME=podman` or `CONTAINER_RUNTIME=docker` to force.
- Node 18+ and npm (for Playwright e2e)
- Optional: Python 3 with `requests` (for `seed-demo-data.py`, `run-demo.py`, `text-ui.py`)

### Podman best practices

- **Rootless:** Podman runs rootless by default; no daemon.
- **Compose:** The scripts prefer **podman-compose** when using Podman (no Docker Compose required). Install with: `pip install podman-compose` (or `pipx install podman-compose`). If you use `podman compose` instead, you must have Docker Compose or podman-compose as the compose provider.
- **DNS:** For service name resolution (e.g. `catcher` from `phase1-tools`), podman-compose sets up the network so containers can reach each other by service name. If using plain Podman pods, the **podman-dnsname** plugin may be needed (e.g. Fedora/RHEL: `sudo dnf install podman-dnsname`).

## 1. Containers for assessment

Use the Phase 1 assessment compose file with the helper script (prefers Podman, falls back to Docker):

```bash
# One command: build, start stack, run scenario
./scripts/phase1-assess.sh

# Or step by step (from repo root):
./scripts/container-compose.sh -f docker-compose.phase1-assess.yml up -d catcher dashboard

# Optional: start the watch client (ingests from clients/docker-client/test-data)
./scripts/container-compose.sh -f docker-compose.phase1-assess.yml up -d client

# Run scenario in tools container
./scripts/container-compose.sh -f docker-compose.phase1-assess.yml run --rm phase1-tools
```

- **Catcher:** http://localhost:8000 (API), http://localhost:8000/health  
- **Dashboard:** http://localhost:5173  

## 2. Individual tool scripts

Scripts in `scripts/tools/` call the catcher API. Use them from the host or inside the `phase1-tools` container. Set `CATCHER_URL` (default `http://127.0.0.1:8000`).

| Script | Purpose |
|--------|--------|
| `scripts/tools/health.sh` | GET /health — exit 0 if ok |
| `scripts/tools/demo-reset.sh` | POST /demo/reset |
| `scripts/tools/sources-register.sh` | POST /sources — args: `source_id [label]` |
| `scripts/tools/sources-list.sh` | GET /sources |
| `scripts/tools/packages-list.sh` | GET /packages — optional query arg, e.g. `?source_id=x` |
| `scripts/tools/buckets.sh` | GET /buckets |
| `scripts/tools/config.sh` | GET /config |
| `scripts/tools/projections.sh` | GET /projections — optional arg: days (default 5) |
| `scripts/tools/ingest-one.sh` | POST /ingest — env: `SOURCE_ID`, `PACKAGE_PATH`, `CHECKSUM`, `SIZE_BYTES`, `TIER_HINT` (optional) |

Examples (from repo root):

```bash
export CATCHER_URL=http://127.0.0.1:8000
./scripts/tools/health.sh
./scripts/tools/sources-register.sh my-source "My label"
SOURCE_ID=my-source PACKAGE_PATH=file.txt CHECKSUM=abc... SIZE_BYTES=0 ./scripts/tools/ingest-one.sh
./scripts/tools/packages-list.sh
./scripts/tools/buckets.sh
```

## 3. Scenario test (script)

Runs the full workflow: health → reset → register source → seed from MANIFEST → assert packages, buckets, sources, config, projections. Exit 0 only if all pass.

**On host (catcher on localhost):**

```bash
CATCHER_URL=http://127.0.0.1:8000 ./scripts/phase1-scenario.sh
```

**Inside containers (Podman or Docker; catcher service name `catcher`):**

```bash
./scripts/container-compose.sh -f docker-compose.phase1-assess.yml run --rm phase1-tools
# Or the all-in-one:
./scripts/phase1-assess.sh
```

The `phase1-tools` image has `CATCHER_URL=http://catcher:8000` set and runs the scenario by default.

## 4. Playwright e2e tests

E2E tests start backend and frontend via `playwright.config.js` if not already running (`reuseExistingServer: true`).

```bash
# Run all e2e tests (dashboard + scenario API test)
npm run test:e2e

# Run only the Phase 1 scenario test (API workflow, no UI)
npx playwright test phase1-scenario

# Run only dashboard tests (including UI and screenshots)
npx playwright test dashboard

# Update snapshots after UI changes
npm run test:e2e:update
```

- **tests/e2e/dashboard.spec.js** — health, dashboard load, sections, packages grid, clients, ingest validation (OpenSpec §7), API endpoints, empty state and “with jobs” screenshots.  
- **tests/e2e/phase1-scenario.spec.js** — single scenario test: health → reset → register → ingest from MANIFEST → assert packages, buckets, sources, config, projections (mirrors `scripts/phase1-scenario.sh`).

## 5. Mock data

Location: **tests/fixtures/mock-data/**  
Manifest: **tests/fixtures/mock-data/MANIFEST.json** (paths, sizes, checksums, tier_hint).

To seed the catcher from the host:

```bash
python3 scripts/seed-demo-data.py --source demo-seed --url http://localhost:8000
```

For a 2-minute demo with accelerated retention (demo mode):

```bash
# Start catcher with DEMO_MODE=1, then:
python3 scripts/run-demo.py
```

## 6. Suggested assessment order

1. Run full assessment: `./scripts/phase1-assess.sh` (starts stack with Podman/Docker, then runs scenario in container).
2. Or manually: start stack with `./scripts/container-compose.sh -f docker-compose.phase1-assess.yml up -d catcher dashboard`, then `... run --rm phase1-tools`.
3. Run Playwright e2e: `npm run test:e2e`
4. Optionally run tools individually and open dashboard at http://localhost:5173

**Cleanup (free ports 8000, 5173):** `./scripts/container-down.sh` stops the assessment stack; `./scripts/container-down.sh --all` also stops the main stack (`docker-compose.yml`).

## 7. Updating baselines

After intentional UI changes:

```bash
npx playwright test --update-snapshots
node scripts/copy-screenshots-to-docs.js   # if you copy screenshots to docs
```
