# TrueNAS Deployment Guide

Host the Edge Backup **dispatcher (Catcher)** and **signal board (dashboard)** on TrueNAS SCALE. Workstation clients and SnarkSentinel send metadata to the NAS; **payload bytes go directly to NAS storage** (SMB/NFS shares or restic repos on the pool).

## Architecture

```
┌─────────────────────┐   metadata/status   ┌──────────────────────────┐
│ Workstation clients │ ──────────────────► │ TrueNAS: Catcher :8000   │
│ SnarkSentinel backup│                     │ SQLite on ZFS dataset    │
└──────────┬──────────┘                     └────────────┬─────────────┘
           │ payload bytes                              │ read-only
           ▼                                            ▼
┌─────────────────────┐                     ┌──────────────────────────┐
│ TrueNAS storage     │                     │ Dashboard (nginx) :8080  │
│ SMB / NFS / restic  │                     │ proxies /api → catcher   │
└─────────────────────┘                     └──────────────────────────┘
```

| Component | Runs on | Persists |
|-----------|---------|----------|
| Catcher API | Docker on TrueNAS | `DATABASE_URL=sqlite:////var/lib/edge-backup/catcher.db` |
| Dashboard | Docker on TrueNAS | Static build only |
| Payload storage | TrueNAS datasets | Client-direct (not through Catcher) |
| OTEL collector | Optional profile | Ephemeral |

## Prerequisites

- TrueNAS SCALE 24.x+ with **Apps / Custom App** or shell access to Docker/Podman Compose
- ZFS dataset for metadata, e.g. `/mnt/tank/edge-backup`
- LAN or Tailscale access from workstations
- Ports: `8000` (API), `8080` (dashboard) — adjust in `.env.truenas`

## Quick deploy

```bash
git clone https://github.com/mowgli42/bookish-train.git
cd bookish-train
cp .env.truenas.example .env.truenas
# Edit TRUENAS_DATA_PATH to your dataset mount
./scripts/truenas-deploy.sh up -d --build
./scripts/truenas-validate.sh
```

Open `http://<truenas-ip>:8080` for the dashboard. API health: `http://<truenas-ip>:8000/health`.

## Environment reference (`.env.truenas`)

| Variable | Default | Purpose |
|----------|---------|---------|
| `TRUENAS_DATA_PATH` | `./data/truenas` | Host path → `/var/lib/edge-backup` in catcher |
| `CATCHER_PORT` | `8000` | Published API port |
| `DASHBOARD_PORT` | `8080` | Published dashboard port |
| `CORS_ORIGINS` | `*` | Restrict in production |
| `LOG_LEVEL` | `INFO` | Catcher log level |

Catcher container env (set in compose):

| Variable | Example | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | `sqlite:////var/lib/edge-backup/catcher.db` | Persist jobs/journal across restarts |
| `DATA_DIR` | `/var/lib/edge-backup` | State directory |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://otel-collector:4318` | Optional tracing |

## TrueNAS SCALE install options

### Option A: Shell + compose (recommended for first deploy)

1. SSH to TrueNAS, clone repo to e.g. `/mnt/tank/apps/bookish-train`
2. Set `TRUENAS_DATA_PATH=/mnt/tank/edge-backup` in `.env.truenas`
3. Run `./scripts/truenas-deploy.sh up -d --build`

### Option B: Custom App

Import `docker-compose.truenas.yml` as a custom compose app. Map the catcher volume to your ZFS dataset.

## Client configuration (workstations)

Point clients at the NAS-hosted Catcher; store payloads on TrueNAS directly.

```bash
export CATCHER_URL=http://192.168.1.50:8000
export SOURCE_ID=melbourne-laptop
export WATCH_DIR=/home/you/Documents
# Payload destination (client-direct, not via Catcher):
export LOCAL_REPOSITORY_DIR=/mnt/truenas-backup/restic
```

SnarkSentinel system backups:

```bash
snarksentinel backup
# transfer-log + package can be ingested or copied to NAS share
```

## Storage patterns

| Pattern | Client config | Catcher role |
|---------|---------------|--------------|
| SMB share | Mount `//truenas/backup` | Metadata only |
| NFS | Mount `truenas:/mnt/tank/backup` | Metadata only |
| restic on pool | `RESTIC_REPOSITORY=/mnt/truenas-backup/restic` | Metadata + manifest tracking |

## Observability (optional)

```bash
TRUENAS_OBSERVABILITY=1 ./scripts/truenas-deploy.sh up -d --build
```

See `docs/OBSERVABILITY-SIGNOZ.md` for OTLP forwarding to SigNoz or compatible backends.

## Security notes

- Restrict Catcher/dashboard to LAN or Tailscale; do not expose without TLS/auth on the public internet
- Use TrueNAS firewall to limit ports 8000/8080 to trusted subnets
- Payload paths and credentials stay on clients; Catcher stores metadata only
- ZFS snapshots on the metadata dataset provide rollback for dispatcher state

## Troubleshooting

| Symptom | Check |
|---------|-------|
| Dashboard empty | `curl http://<nas>:8000/health` — `jobs_count` should increment after client ingest |
| State lost on restart | Verify `DATABASE_URL` and volume mount for `/var/lib/edge-backup` |
| Client cannot reach Catcher | Firewall, `CATCHER_URL`, NAS IP/DNS |
| Compose fails | `./scripts/container-compose.sh -f docker-compose.truenas.yml config` |

Validation script:

```bash
CATCHER_URL=http://127.0.0.1:8000 ./scripts/truenas-validate.sh
```

## Related docs

- `docs/DEPLOYMENT.md` — general deployment
- `docs/PERSONAL-COMPUTER-MVP.md` — home backup MVP
- `docs/OBSERVABILITY-SIGNOZ.md` — OTEL/SigNoz
- SnarkSentinel: `docs/BOOKISH_TRAIN_INTEGRATION.md` (snarksentinel repo)

## Epic tracking

Implements bookish-train issues #16–#21 (TrueNAS server packaging epic).
