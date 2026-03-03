# Proposal: Next Logical Step — Restic + Containers Prototype

**Goal:** Working end-to-end prototype where restic performs real backups to containerized storage, and the Catcher tracks metadata. All components run in containers.

---

## Current State (OpenSpec §2, §10.2)

| Component | Status | Notes |
|-----------|--------|-------|
| **Phase 1 Prototype** | Done | Docker: catcher, client, dashboard |
| **docker-client** | Watches dir, POSTs metadata only | No actual backup storage |
| **restic-rclone-backup.py** | Exists, runs restic | Outside containers; needs RESTIC_REPOSITORY |
| **Storage transport** | Phase 4 in spec | rclone + restic; not yet in prototype |

**Gap:** The prototype has no real backup storage. The client POSTs file metadata; restic-rclone-backup.py can run restic but requires external RESTIC_REPOSITORY (e.g. S3).

---

## Next Logical Step: Restic + MinIO in Containers

Bring restic into the container stack with S3-compatible storage so the prototype is self-contained.

```
                    ┌─────────────────────────────────────────────────────────────┐
                    │  CURRENT: docker-client → POST /ingest (metadata only)       │
                    └─────────────────────────────────────────────────────────────┘

                    ┌─────────────────────────────────────────────────────────────┐
                    │  TARGET: restic-client → restic backup → MinIO (S3)          │
                    │           ↓                                                 │
                    │      POST/PATCH /ingest (metadata + progress)                 │
                    └─────────────────────────────────────────────────────────────┘

  ┌──────────────┐     restic backup      ┌──────────────┐     POST/PATCH      ┌──────────────┐
  │ restic-client│ ──────────────────────►│    MinIO     │                     │   Catcher    │
  │ (watch dir,  │     s3:minio/restic    │ (S3-compat   │                     │ (metadata)   │
  │  run restic) │                        │  storage)   │                     │              │
  └──────────────┘                        └──────────────┘                     └──────────────┘
         │                                       │                                      │
         └───────────────────────────────────────┴──────────────────────────────────────┘
                              docker-compose network
```

---

## Components

### 1. MinIO (storage container)

- **Role:** S3-compatible object storage for restic repository.
- **Image:** `minio/minio` or `quay.io/minio/minio`.
- **Config:** Create bucket `restic`; expose port 9000 (API) and 9001 (console).
- **restic repo URL:** `s3:http://minio:9000/restic`

### 2. restic-client (new container)

- **Role:** Watch a directory, run restic backup to MinIO, report progress to Catcher.
- **Base:** Reuse `scripts/restic-rclone-backup.py` or embed its logic.
- **Env:** `CATCHER_URL`, `RESTIC_REPOSITORY=s3:http://minio:9000/restic`, `RESTIC_PASSWORD`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` (MinIO credentials).
- **Volumes:** `./clients/docker-client/test-data:/data:ro` (or similar) for backup source.
- **Flow:** On schedule or file change → `restic backup /data` → POST /ingest → PATCH progress → PATCH completed.

### 3. docker-compose changes

- Add `minio` service.
- Add `restic-client` service (or replace `client` with restic-client).
- Ensure `restic-client` depends on `catcher` and `minio`; waits for MinIO to be ready.

---

## Implementation Options

| Option | Effort | Scope |
|--------|--------|-------|
| **A) Add restic-client + MinIO** | Medium | New container; keep existing docker-client for metadata-only demos. |
| **B) Replace docker-client with restic-client** | Medium | Single client; restic is the only backup path. |
| **C) Hybrid: docker-client + optional restic-client** | Low | Add MinIO + restic-client; docker-client unchanged. User chooses which to run. |

**Recommendation:** A or C. Keep docker-client for quick metadata demos; add restic-client for real backup demos. Minimal diff.

**Implemented (Option C):** MinIO + restic-client added. Run `docker compose up client` for metadata-only, or `docker compose up restic-client` (with catcher, minio) for real restic backup.

---

## Prerequisites

- **restic** in restic-client image (install via apt/apk or use restic image as base).
- **MinIO** default credentials or env vars for `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`.
- **restic init** on first run (or init in Dockerfile/entrypoint if bucket is empty).

---

## OpenSpec Alignment

- **§2.1:** Storage transport is "—" for Phase 1; this proposal brings restic forward into the prototype.
- **§2.2:** restic for full backup; this is a single-tier (MinIO) demo; replicate_to_all / multi-tier is Phase 4.
- **§10.2 Phase 4:** "restic (replicated backups)" — this prototype validates restic integration; full tier flow is later.

---

## Validation

- `docker compose up` → restic-client backs up test-data to MinIO.
- Catcher shows job: in_progress → completed.
- Dashboard shows package in appropriate bucket (hot, per rule set).
- `restic snapshots` (run inside restic-client or via exec) lists backups in MinIO.

---

## NOT in scope (this step)

- rclone or tier transitions (Phase 4).
- Multiple storage backends or offsite.
- restic prune/forget by retention rules (Catcher does not drive restic lifecycle yet).
- Windows client (Phase 2).
