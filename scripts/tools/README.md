# Phase 1 assessment tools

Shell scripts that call the catcher API. Use individually or via `scripts/phase1-scenario.sh`.

**Environment:** `CATCHER_URL` (default `http://127.0.0.1:8000`). In Docker use `http://catcher:8000`.

| Script | Description |
|--------|-------------|
| `health.sh` | GET /health — exit 0 if status ok |
| `demo-reset.sh` | POST /demo/reset |
| `sources-register.sh` | POST /sources — args: `source_id [label]` |
| `sources-list.sh` | GET /sources |
| `packages-list.sh` | GET /packages — optional: `?source_id=...` |
| `buckets.sh` | GET /buckets |
| `config.sh` | GET /config |
| `projections.sh` | GET /projections — optional arg: days (default 5) |
| `ingest-one.sh` | POST /ingest — env: SOURCE_ID, PACKAGE_PATH, CHECKSUM, SIZE_BYTES, TIER_HINT |

**Build tools image:** From repo root: `podman build -f scripts/tools/Dockerfile -t phase1-tools .` (or `docker build ...`).

**Run scenario in container:** `./scripts/phase1-assess.sh` or `./scripts/container-compose.sh -f docker-compose.phase1-assess.yml run --rm phase1-tools` (uses Podman if available, else Docker).
