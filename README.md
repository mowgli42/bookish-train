# Edge Backup System

**Treat edge devices as cattle, not pets.** Data does not reside on the edge. It is packaged, tracked, and stored in cloud or offsite storage. This repo implements an end-to-end backup strategy with minimal tooling: a **Catcher** API that tracks metadata, **restic** and **rclone** for actual storage transport, and **web** or **text UI** for monitoring.

---

## What We're Building

| Component | Role |
|-----------|------|
| **Catcher** | Central API that tracks backup jobs, sources, buckets, and retention. It does *not* store backup payloads—only metadata. |
| **Edge clients** | Scripts (Python, restic, rclone) that backup data and POST metadata to the Catcher. |
| **Storage** | restic (dedup, integrity) and rclone (tier transfers). Phase 4 integrates S3, GCS, local, etc. |
| **Monitoring** | Web dashboard (Svelte) or Text UI (terminal) show status, buckets, packages, and projections. |

---

## Architecture

```
                    ┌─────────────────────────────────────────────────────────┐
                    │                    CATCHER (FastAPI)                     │
                    │  Tracks: packages, sources, buckets, retention rules     │
                    │  APIs: POST /ingest, PATCH /packages, GET /status, etc.  │
                    └──────────────────────────┬──────────────────────────────┘
                                               │
         ┌─────────────────────────────────────┼─────────────────────────────────────┐
         │                                     │                                     │
         ▼                                     ▼                                     ▼
┌─────────────────┐               ┌─────────────────────┐               ┌─────────────────────┐
│  EDGE CLIENTS   │               │   RESTIC / RCLONE   │               │   MONITORING        │
│  - watch dir    │  POST /ingest │   (actual storage)  │  GET /status  │   - Web Dashboard   │
│  - restic       │ ─────────────►│   - restic backup   │ ◄─────────────│   - Text UI         │
│  - rclone       │  PATCH prog   │   - rclone copy     │               │     (--live)        │
└─────────────────┘               └─────────────────────┘               └─────────────────────┘
```

---

## Data Flow (with screenshots)

Data flows **Clients → Hot → Warm → Cold → Offsite**. Retention rules (per package type) determine when packages transition between tiers. The dashboard visualizes this as a train: each car is a bucket, with incoming and outgoing package counts.

### 1. Web Dashboard — Data Flow View

![Dashboard with packages — train-style data flow](docs/dashboard-with-jobs.png)

*Clients (sources) send packages into Hot; packages age and move Warm → Cold → Offsite per retention rules.*

### 2. Web Dashboard — Empty State

![Dashboard empty state](docs/dashboard-empty.png)

*Component status, buckets, packages, clients, retention rules, and projections.*

### 3. Text UI — Terminal Monitoring

![Text UI display](docs/text-ui.svg)

*Same data in the terminal. Use `python scripts/text-ui.py --live` to watch uploads in real time.*

---

## API Reference

Base path: `http://localhost:8000/api/v1` (or `CATCHER_URL`).

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/ingest` | Register a backup job. Body: `{ "source_id", "path", "checksum?", "size_bytes?", "package_type?" }`. Returns `{ "job_id" }`. |
| `PATCH` | `/packages/{id}` | Update progress or status. Body: `{ "progress_percent?", "checksum?", "status?" }`. |
| `GET` | `/packages` | List packages. Query: `?status=`, `?source_id=`, `?bucket=`. |
| `GET` | `/packages/{id}` | Get one package. |
| `GET` | `/sources` | List registered sources. |
| `POST` | `/sources` | Register source: `{ "source_id", "label?" }`. |
| `GET` | `/buckets` | Bucket counts and storage per tier. |
| `GET` | `/config` | Retention rule sets (hot/warm/cold/offsite per package type). |
| `GET` | `/projections` | Upcoming transitions: `?days=5` or `?seconds=10` (demo). |
| `GET` | `/status` | Component status (clients, catcher, buckets). |

**Ingest body (POST /ingest):**

```json
{
  "source_id": "my-laptop",
  "path": "backup/2024-01/data",
  "checksum": "sha256-hex (required when size_bytes > 0)",
  "size_bytes": 1024000,
  "package_type": "user_data | app_logs | audit_logs | business_data | job_package | cache"
}
```

**Package patch body (PATCH /packages/{id}):**

```json
{ "progress_percent": 75, "status": "in_progress" }
{ "progress_percent": 100, "checksum": "sha256...", "status": "completed" }
```

---

## Restic & Rclone Prototype

Per [OpenSpec §2.2](openspec/specs/edge-backup-system.md): **rclone** for 7z-compressed tier transfers; **restic** for full replicated backups. A prototype script reports backup progress to the Catcher:

```bash
# Install
pip install requests

# Mock mode (no restic/rclone) — simulates 0–100% over 10 seconds
python scripts/restic-rclone-backup.py --mock --path backup/demo

# Restic (requires RESTIC_REPOSITORY)
export RESTIC_REPOSITORY=s3:s3.amazonaws.com/my-bucket
python scripts/restic-rclone-backup.py --tool restic --path /data/to/backup

# Rclone (requires rclone configured)
python scripts/restic-rclone-backup.py --tool rclone --from /local/path --to remote:bucket/path
```

The script:
1. `POST /ingest` — registers the job
2. Runs restic backup or rclone copy
3. `PATCH /packages/{id}` — updates `progress_percent` during transfer
4. `PATCH /packages/{id}` — sets `status=completed` when done

---

## Monitoring Uploads with the Text UI

Run the backup in one terminal and the Text UI in another:

```bash
# Terminal 1: Start catcher and run a mock backup
cd backend && uvicorn main:app --port 8000 &
python scripts/restic-rclone-backup.py --mock --path backup/demo --duration 15

# Terminal 2: Watch progress live
python scripts/text-ui.py --live
```

The Text UI refreshes every 3 seconds (or `--refresh 5`). Packages show status (`in_progress`), `progress_percent`, and move to `completed` when done.

---

## Quick Start

**Backend**

```bash
cd backend && pip install -r requirements.txt && uvicorn main:app --port 8000
```

**Frontend**

```bash
cd frontend && npm install && npm run dev
```

Open http://localhost:5173.

**Text UI (terminal alternative)**

```bash
pip install -r scripts/requirements-text-ui.txt
python scripts/text-ui.py              # One-shot
python scripts/text-ui.py --live      # Live refresh
```

**Seed demo data**

```bash
python scripts/seed-demo-data.py
```

**Docker**

```bash
docker compose up --build
```

---

## Project Structure

```
├── backend/           # Catcher (FastAPI)
├── frontend/          # Web dashboard (Svelte)
├── clients/           # Docker client, watch-and-ingest
├── scripts/
│   ├── text-ui.py              # Terminal UI (--live for monitoring)
│   ├── restic-rclone-backup.py # Restic/rclone → Catcher prototype
│   ├── seed-demo-data.py
│   └── run-demo.py
├── docs/              # Screenshots, deployment
└── openspec/specs/    # edge-backup-system.md (single source of truth)
```

---

## Phases

| Phase | Scope |
|-------|--------|
| **1** | Catcher API, Svelte dashboard, Text UI, Docker client |
| **2** | Windows endpoint agent |
| **3** | Linux/macOS, NFS sources |
| **4** | Cloud storage tiers; rclone (7z transfers); restic (replicated backups) |

---

## Screenshots

To refresh screenshots:

```bash
npx playwright install chromium
npm run capture-screenshots
python scripts/text-ui.py --save-svg docs/text-ui.svg
```

---

## Development

- **OpenSpec:** `openspec/specs/edge-backup-system.md` — propose changes there first.
- **Beads:** `./scripts/beads-setup.sh` — task tracking.
- **Validation:** `npm run test:e2e` — Playwright tests.

See [docs/VALIDATION-WORKFLOW.md](docs/VALIDATION-WORKFLOW.md) and [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).
