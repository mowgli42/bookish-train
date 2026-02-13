# Edge Backup System — Deployment Guide

This document describes **where each component runs** and how to deploy clients, catcher (backend), and dashboard (frontend).

---

## Data Flow Overview

```
┌──────────────────┐   POST /ingest    ┌─────────────────────┐
│  EDGE CLIENTS    │ ─────────────────►│  CATCHER (backend)  │
│  (one per device)│   packaged blobs  │  Central server     │
└──────────────────┘                   └──────────┬──────────┘
        │                                          │
        │ watch local folders                      │ rule sets
        │ package new/changed                      │ assign buckets
        ▼                                          ▼
   Local staging only                    ┌─────────────────────┐
   (no durable data)                     │  STORAGE TIERS       │
                                         │  hot → warm → cold   │
                                         │  → offsite          │
                                         └─────────────────────┘
```

Data originates on edge devices, is packaged by clients, sent to the catcher, and ( Phase 4) stored in cloud or offsite tiers. The dashboard shows this flow: sources, streams, buckets, rule sets, and projections.

---

## Component Placement

| Component | Where to deploy | Notes |
|-----------|-----------------|-------|
| **Edge clients** | On each edge device (Windows, Linux, or Docker) | Watch local folders; POST to catcher URL. One client per machine or per watch path. |
| **Catcher (backend)** | Central server (cloud VM, on-prem, or container) | Single instance for Phase 1–2. Exposes `/api/v1/*`. Can serve frontend static files or run separately. |
| **Frontend (dashboard)** | Same host as catcher or CDN | Static SPA; bundle and serve from catcher or deploy to S3/CloudFront, Vercel, Netlify, etc. |
| **Storage (Phase 4)** | Cloud object storage (S3, GCS, Azure Blob) / offsite | Hot/warm/cold buckets; lifecycle rules applied per retention config. |

---

## 1. Edge Clients

Deploy on each device that produces backup data.

- **Phase 1 (Docker):** `clients/docker-client/watch_and_ingest.py` in a container; points to catcher via `CATCHER_URL`.
- **Phase 2 (Windows):** Agent script or compiled .exe; same API. Deploy via script, installer, or fleet tooling.
- **Phase 3:** Linux, macOS, NFS watchers.

**Configuration (per client):**

- `CATCHER_URL` — Base URL of the catcher (e.g. `https://catcher.example.com`)
- `WATCH_DIR` — Local path to watch (e.g. `C:\Backup\Data` or `/var/backup`)

Clients need network connectivity to the catcher. No authentication in Phase 1; add auth in later phases.

---

## 2. Catcher (Backend)

Deploy on a central server reachable by all clients.

**Options:**

- **Docker:** `docker compose up` (see `docker-compose.yml`). Catcher runs on port 8000.
- **Manual:** `cd backend && uvicorn main:app --host 0.0.0.0 --port 8000`
- **Production:** Behind reverse proxy (nginx, Caddy); TLS termination at proxy.

**Environment:**

- No required env vars for Phase 1. In-memory store; restart clears data.
- Phase 2+: Add `DATABASE_URL` for SQLite/PostgreSQL when persisted storage is implemented.

**Health check:** `GET /health` returns `{"status":"ok"}`.

---

## 3. Frontend (Dashboard)

The dashboard is a static Svelte app. Two deployment patterns:

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

- **Clients → Catcher:** HTTPS (or HTTP for dev). Clients POST to `/api/v1/ingest`.
- **Dashboard → Catcher:** Same-origin or CORS; catcher has `allow_origins=["*"]` for dev; tighten for production.
- **Catcher → Storage (Phase 4):** Outbound to cloud provider APIs.

---

## 5. Quick Reference

| Scenario | Commands |
|----------|----------|
| Local dev (no Docker) | Backend: `uvicorn main:app --reload --port 8000`; Frontend: `npm run dev`; Client: `python clients/docker-client/watch_and_ingest.py` |
| Docker prototype | `docker compose up --build` |
| Seed demo data | `python scripts/seed-demo-data.py` (with catcher running) |

---

See `openspec/specs/edge-backup-system.md` for architecture, API, and retention rules.
