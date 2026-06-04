# Container Setup: Dispatcher API and Signal Board

This guide runs the status/control plane as containers for home use:

- **Dispatcher API** (`catcher` service): tracks manifests, status, routes, resume work, journal, and config snapshots.
- **Signal Board** (`dashboard` service): web status page that reads the dispatcher API.

The clients/engines still move data directly to storage stations. The containers below do not move payload data.

## Home safety defaults

- Bind to your LAN or localhost only unless you deliberately add TLS/auth.
- Do not expose the dashboard or API directly to the public internet.
- Treat the current app as a development/home-lab service until passkey/redaction work is implemented.
- Put the containers behind a trusted reverse proxy if you need remote access.

## Prerequisites

Use Docker or Podman. The repo helper detects either:

```bash
./scripts/container-compose.sh --help
```

## Start API + status page

From the repo root:

```bash
./scripts/container-compose.sh -f docker-compose.yml up -d --build catcher dashboard
```

Open:

```text
Dispatcher API health: http://127.0.0.1:8000/health
Signal Board:          http://127.0.0.1:5173
Packages page:         http://127.0.0.1:5173/#packages
```

## Run the repository demo against containers

```bash
python3 scripts/client-repository-demo.py \
  --catcher-url http://127.0.0.1:8000 \
  --source-id linux-desktop-demo \
  --s3-uri s3://idrive-e2-demo/linux-desktop
```

Expected result:

- local repository copies under `/tmp/edge-client-repository-demo/repositories/local`
- S3-style demo copies under `/tmp/edge-client-repository-demo/repositories/s3`
- completed `local/...` and `s3/...` rows in the Signal Board Packages page

## Start full prototype stack

The default compose file includes the demo client service:

```bash
./scripts/container-compose.sh -f docker-compose.yml up -d --build
```

Current compose services:

| Service | Purpose | Port |
|---------|---------|------|
| `catcher` | Dispatcher API compatibility service | `8000` |
| `dashboard` | Signal Board web UI | `5173` |
| `client` | Prototype watch client | none |

## Logs and status

```bash
./scripts/container-compose.sh -f docker-compose.yml ps
./scripts/container-compose.sh -f docker-compose.yml logs catcher
./scripts/container-compose.sh -f docker-compose.yml logs dashboard
```

API checks:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/api/v1/packages
curl http://127.0.0.1:8000/api/v1/status
```

## Stop containers

```bash
./scripts/container-compose.sh -f docker-compose.yml down
```

## Current limitations

- Dispatcher state is still in-memory in the current prototype; restart clears runtime package status.
- Passkey unlock and dashboard redaction are planned, not implemented.
- Real IDrive e2 and OneDrive transport are planned through restic/rclone tasks.
- Use this container setup for home-lab validation, not unattended daily protection yet.

See:

- `docs/RAILWAY-ARCHITECTURE.md`
- `docs/HOME-RELIABILITY-RANSOMWARE.md`
- `clients/docker-client/README.md`
