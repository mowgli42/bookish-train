# Friend Quickstart — Edge Backup Railway

Try the **bookish train** dashboard in a few minutes. No auth; data lives in memory until you restart the Catcher.

## What you need

| Tool | Version |
|------|---------|
| **Git** | any recent |
| **Node.js** | 18+ |
| **Python** | 3.10+ |
| **Podman** or **Docker** | optional but easiest for full stack |

## Option A — Containers (recommended)

```bash
git clone https://github.com/mowgli42/bookish-train.git
cd bookish-train
./scripts/up.sh
```

Open **http://127.0.0.1:5173** (dashboard) and **http://127.0.0.1:8000/health** (API).

Seed sample packages:

```bash
python3 scripts/seed-demo-data.py
```

Refresh the dashboard — you should see packages on the **Packages** page and movement on **Tracks**.

Stop everything:

```bash
./scripts/container-down.sh
```

## Option B — Local dev (no containers)

```bash
git clone https://github.com/mowgli42/bookish-train.git
cd bookish-train
npm install
cd frontend && npm install && cd ..

# Terminal 1 — API
./scripts/run-backend.sh

# Terminal 2 — dashboard
cd frontend && npm run dev
```

Then seed: `python3 scripts/seed-demo-data.py`

Or one command (starts backend + frontend):

```bash
npm run serve
```

## Option C — 2-minute animated demo

Retention runs in **seconds** so you can watch tiers change quickly.

```bash
# Terminal 1
DEMO_MODE=1 ./scripts/run-backend.sh

# Terminal 2
cd frontend && npm run dev

# Terminal 3
pip install requests   # if needed
python3 scripts/run-demo.py
```

Watch the **Tracks** and **Packages** pages during the script.

## Things to click

1. **Tracks** — train-style bucket flow and migration rules grid.
2. **Packages** — grid of ingested jobs (filter by bucket/status).
3. **Rules** — edit retention stops per package type.
4. **Settings** — apply a **scenario preset** (cloud / on-prem / cost); in demo mode, **Seed data**.

## Terminal UI (optional)

```bash
pip install -r scripts/requirements-text-ui.txt
python3 scripts/text-ui.py --live
```

## Restic + MinIO (real backup prototype)

With `./scripts/up.sh`, the stack includes MinIO and `restic-client`. Sample files come from `tests/fixtures/mock-data/` (mounted into clients). Check MinIO console at **http://127.0.0.1:9001** (login `minioadmin` / `minioadmin`).

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Port 8000 or 5173 in use | `PORT=8001 ./scripts/run-backend.sh` and set `VITE_PROXY_API` in frontend |
| Empty dashboard | Run `python3 scripts/seed-demo-data.py` or Settings → Seed (demo mode) |
| `npm run serve` fails | Run `./scripts/run-backend.sh` in one terminal, `cd frontend && npm run dev` in another |
| Playwright tests | `npx playwright install chromium` then `npm run test:e2e` |

## Caveats (honest)

- **No login** — local demo only.
- **No database** — restart the Catcher and metadata is gone.
- **Rules assign buckets in metadata** — actual storage moves are Phase 4.

More detail: [README](../README.md), [VALIDATION-WORKFLOW.md](VALIDATION-WORKFLOW.md).
