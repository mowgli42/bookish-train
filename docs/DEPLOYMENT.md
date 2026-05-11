# Edge Backup System — Deployment Guide

This document describes **where each component runs** and how to deploy engines/clients, the dispatcher API (formerly Catcher backend), and the signal-board dashboard.

---

## Data Flow Overview

```
┌──────────────────┐ metadata/status ┌─────────────────────┐
│  ENGINES         │ ───────────────►│  DISPATCHER API     │
│  (clients)       │                 │  Control plane      │
└────────┬─────────┘                 └──────────┬──────────┘
         │ payload bytes                         │ read-only status
         ▼                                       ▼
┌──────────────────┐                  ┌─────────────────────┐
│  STATIONS/YARDS  │                  │  SIGNAL BOARD       │
│  TrueNAS/local   │                  │  Dashboard/Text UI  │
│  OneDrive/S3     │                  └─────────────────────┘
│  restic repo     │
└──────────────────┘
```

Data originates on edge devices, is packaged by clients/engines, and is moved by those clients directly to storage stations/yards. The dispatcher API tracks manifests, status, routes, resume work, configuration snapshots, and journal events. The dashboard/signal board shows this flow; it does not move payload data.

---

## Component Placement

| Component | Where to deploy | Notes |
|-----------|-----------------|-------|
| **Engines / clients** | On each edge device (Windows, Linux, macOS, or Docker) | Watch local folders, move data to stations/yards, verify checksums, POST manifests/status to dispatcher. |
| **Dispatcher API (Catcher compatibility name)** | Central server (cloud VM, on-prem, or container) | Control plane for `/api/v1/*`: manifests, status, routes, resume, config snapshots, journal. |
| **Signal Board (dashboard)** | Same host as dispatcher or CDN | Static SPA; reads dispatcher status. Does not move payload data. |
| **Stations / yards** | TrueNAS/NAS, local repo, S3/IDrive e2, OneDrive/rclone, restic repo | Durable storage destinations. Clients move payload bytes here. |

---

## 1. Engines / Clients

Deploy on each device that produces backup data.

- **Phase 1 (Docker):** `clients/docker-client/watch_and_ingest.py` in a container; points to dispatcher via `CATCHER_URL` for compatibility.
- **Phase 2 (Windows):** Agent script or compiled .exe; same API. Deploy via script, installer, or fleet tooling.
- **Phase 3:** Linux, macOS, NFS watchers.

**Configuration (per client):**

- `CATCHER_URL` — Base URL of the catcher (e.g. `https://catcher.example.com`)
- `WATCH_DIR` — Local path to watch (e.g. `C:\Backup\Data` or `/var/backup`)

Clients need network connectivity to the dispatcher API and storage stations/yards. No authentication in Phase 1; add auth in later phases.

---

## 2. Dispatcher API (Catcher Backend)

Deploy on a central server reachable by all clients. The dispatcher tracks control-plane state only; engines/clients move payload data to storage.

**Options:**

- **Containers (Podman or Docker):** `./scripts/container-compose.sh up -d` (see `docker-compose.yml`). Catcher runs on port 8000.
- **Manual:** `cd backend && uvicorn main:app --host 0.0.0.0 --port 8000`
- **Production:** Behind reverse proxy (nginx, Caddy); TLS termination at proxy.

**Environment:**

- No required env vars for Phase 1 prototype: without `CATCHER_SQLITE_PATH` or SQLite `DATABASE_URL`, the dispatcher uses an in-memory store (restart clears data).
- **Optional SQLite:** set `CATCHER_SQLITE_PATH` to a file path (e.g. `/var/lib/edge-backup/catcher.db`) or `DATABASE_URL=sqlite:////absolute/path.db` so packages, sources, yard ledger, config snapshots, and active rule sets survive restarts. PostgreSQL remains a later scale-up option.

**Health check:** `GET /health` returns `{"status":"ok"}`.

---

## 3. Signal Board (Dashboard)

The dashboard is a static Svelte app. It reads dispatcher status and does not move payload bytes. Two deployment patterns:

### Option A: Served by Catcher

Build and serve from the same host:

```bash
cd frontend && npm run build
# Copy dist/ to backend static dir or serve via nginx
```

If using FastAPI static files: mount `frontend/dist` at `/` and proxy `/api` to the API. See `backend/main.py` or add `StaticFiles` mount for production.

### Option B: Separate Host (CDN, Vercel, etc.)

1. Build: `cd frontend && npm run build`
2. Deploy `dist/` to S3, Vercel, Netlify, or any static host.
3. Configure API base URL: set `VITE_API_BASE` or equivalent so fetch calls hit the catcher (e.g. `https://catcher.example.com`).

Vite dev server proxies `/api` to `http://localhost:8000` by default; production must point to the real catcher URL.

---

## 4. Network Requirements

- **Engines → Dispatcher:** HTTPS (or HTTP for dev). Clients POST manifests/status to `/api/v1/ingest` and related endpoints.
- **Engines → Stations/Yards:** SMB/NFS/local filesystem, rclone, S3/IDrive e2, OneDrive, restic, or other configured storage transports.
- **Signal Board → Dispatcher:** Same-origin or CORS; dispatcher has `allow_origins=["*"]` for dev; tighten for production.

---

## 5. Quick Reference

| Scenario | Commands |
|----------|----------|
| Local dev (no Docker) | Backend: `uvicorn main:app --reload --port 8000`; Frontend: `npm run dev`; Client: `python clients/docker-client/watch_and_ingest.py` |
| Container prototype | `./scripts/container-compose.sh up -d --build` (Podman or Docker) |
| Seed demo data | `python scripts/seed-demo-data.py` (with catcher running) |

---

See `openspec/specs/edge-backup-system.md` for architecture, API, and retention rules.

For a focused container walkthrough for the dispatcher API and Signal Board, see `docs/CONTAINER-SETUP.md`.
