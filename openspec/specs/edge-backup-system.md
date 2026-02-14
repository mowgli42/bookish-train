# Edge Backup System — Single Source of Truth

**Goal:** Treat edge devices as cattle, not pets. Data must not reside on the edge; it is packaged, tracked, and stored in cloud or offsite storage. End-to-end execution of a data backup strategy using minimal tooling.

---

## 1. System Architecture

### 1.1 Data Flow: Sources → Streams → Buckets

```
┌──────────────────┐                    ┌─────────────────────┐
│  SOURCES         │   POST /ingest     │  CATCHER (backend)  │
│  (edge clients)  │ ─────────────────►│  Tracks metadata    │
│  - Windows agent │   packaged blobs   │  Applies rule sets  │
│  - Linux/Docker  │                    │  Assigns to buckets│
│  - NFS watcher   │                    └──────────┬─────────┘
└──────────────────┘                               │
        │                                           │ rule sets
        │ watch folders                             │ (retention)
        │ package new/changed                        ▼
        ▼                                    ┌─────────────────────┐
   Local staging only                        │  BUCKETS            │
   (no durable data)                         │  hot → warm → cold  │
                                             │  → offsite          │
                                             └─────────────────────┘
```

- **Sources:** Edge clients (scripts) that watch folders. Each `source_id` is a **stream** of data into the catcher.
- **Streams:** Ingest flow from a source; data is categorized by age and rule sets into buckets.
- **Buckets:** Logical storage tiers—**hot** (recent), **warm** (cache), **cold** (archive), **offsite** (long-term). Data moves between buckets per rule sets.
- **Rule sets:** Retention policies (e.g. "hot 7d → warm 30d → cold 1y") determine when objects transition. See §8.

### 1.2 Old vs New Data; Unutilized; Projections

| Concept | Meaning |
|---------|---------|
| **New data** | Recently ingested (&lt; hot retention); in hot bucket. |
| **Old data** | Aged per rule set; transitions warm → cold → offsite. |
| **Unutilized** | No access since ingest; eligible for lifecycle (e.g. 90-day rule moves to cold). |
| **Projection** | "In next N days, which objects will transition?" — from rule sets + `created_at`. |

### 1.3 Dashboard Requirements

The dashboard is **compact** and organized around **component status** as the primary connection to backend services. Each status element (Client, Catcher, Buckets) is clickable and scrolls to the corresponding section.

1. **Component status:** Client, Catcher, Buckets (deleted count). Links to #buckets, #packages, #rules. Indicates backend connectivity.
2. **Buckets:** Train-style data flow visualization—**Clients** (sources) → **Hot** → **Warm** → **Cold** → **Offsite**. Rectangular, train-like cars. Each bucket shows: incoming package count (left), tier name + files + storage (center), outgoing count to next tier (right). Client car shows source names and new packages flowing to Hot.
3. **Packages** (formerly jobs): Scrollable, filterable list. Each row expandable (dropdown) for details. Progress bar for initial upload. When hash is computed, display it.
4. **Retention rulesets:** View active rules. MVP: method to update retention (PATCH /config).
5. **Projections:** Upcoming transitions.
6. **Deleted data:** Messaging that updated data is always coming in; delete oldest, keep latest.

### 1.4 Dashboard DataGrid Technology

The dashboard uses **@svar-ui/svelte-grid** (SVAR Grid) for Packages, Clients, and Retention Rules. This choice is documented here to guide future enhancements.

| Requirement | SVAR Grid Support |
|-------------|-------------------|
| Filters | Built-in `text` and `richselect`; per-column filter config |
| Advanced filters | `@svar-ui/svelte-filter` (FilterBar, FilterBuilder) integrates with Grid API |
| Colors/styling | `cellStyle`, `rowStyle`, `columnStyle`; custom cell components; WillowDark theme; CSS variables |
| Svelte 5 | Native support |

**Short-term improvements (tracked in Beads):**
- Use `richselect` for package_type column (all types as options)
- Add filter config (search icon, clear button) on text columns
- Use `cellStyle` for bucket column (replaces `cellClass`)
- Override WillowDark CSS variables for clearer contrast

**Medium-term:** Add `@svar-ui/svelte-filter` FilterBar above Packages grid for multi-field AND/OR filtering.

**Alternatives considered:** TanStack Table (headless, more setup), AG Grid (commercial license for advanced features), Vincjo/Datatables (fewer features). SVAR remains the preferred option for Svelte 5.

- **Removed:** Data Flow description section (redundant).

---

## 2. Phases (High Level)

| Phase | Scope | Deliverable |
|-------|--------|-------------|
| **1** | Prototype | Docker-based catcher + client containers; ingest API; minimal UI to track jobs. |
| **2** | MVP | Windows endpoint package: agent script monitoring local folders, forwarding to catcher. |
| **3** | Extend clients | Additional client types (Linux, macOS) and optional network filesystem sources. |
| **4** | Storage tiers | Cloud tiers (hot/warm/cold) and offsite storage integration; lifecycle rules. |

### 2.1 Technology Selection by Phase

Technologies may differ across phases; the **toolbox** grows and remains usable. Scripts from prototype can be deployed in production when the target supports them.

| Area | Prototype (Phase 1) | MVP (Phase 2) | Production |
|------|---------------------|---------------|------------|
| **Edge client** | Python script in Docker | Python script; optionally batch/PowerShell; PyInstaller-compiled `.exe` for Windows | Same toolbox: choose per target (batch, Python, compiled Python, Ansible-managed) |
| **Deployment** | Docker Compose | Manual or scripted; optional Ansible for fleet | Ansible playbooks, container orchestration, or script-based install |
| **Catcher** | FastAPI, in-memory store | FastAPI, SQLite or file-based | FastAPI, DB (PostgreSQL/SQLite) per scale |
| **Dashboard** | Svelte (IxDF-aligned) | Svelte | Svelte |
| **Validation** | Playwright (API + UI capture) | Playwright per phase | Playwright in CI; screenshots in docs |

**Toolbox principle:** Always have working code. Each phase adds artifacts (batch scripts, Ansible playbooks, compiled binaries) to `scripts/` or `clients/`; if production supports script deployment, use the existing toolbox rather than rewriting.

### 2.2 User Interface (IxDF)

The Web Dashboard and any end-user interfaces follow **Interaction Design Foundation (IxDF)** principles for clarity and usability.

- **Affordances:** Controls and actions are perceivable; users infer behavior from appearance (e.g., refresh button clearly indicates manual refresh).
- **Signifiers:** Cues communicate what is interactive (links, buttons, status badges) and what is informational (labels, timestamps).
- **Consistency:** Patterns reused across views (e.g., job lists, status indicators); conventions respected (underlined links, primary actions emphasized).
- **Feedback:** Status changes are visible (loading states, success/error messages); no silent failures.
- **Simplicity:** Read-only dashboard; minimal navigation; no hidden or complex workflows.

Reference: [Interaction Design Foundation](https://www.interaction-design.org/) — affordances, signifiers, usability heuristics.

---

## 3. API Endpoints (Catcher)

Base path: `/api/v1`. All request/response bodies are JSON.

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/ingest` | Accept a packaged backup payload. Returns `package_id` (alias `job_id`). |
| `GET` | `/packages` | List packages (optional: `?status=...`, `?source_id=...`, `?bucket=...`). Alias: `/jobs`. |
| `GET` | `/packages/{id}` | Get one package (progress, checksum when computed, bucket). Alias: `/jobs/{id}`. |
| `PATCH` | `/packages/{id}` | Update progress or checksum (upload in progress). |
| `GET` | `/sources` | List registered sources (edge endpoints / streams). |
| `POST` | `/sources` | Register a source (e.g. `source_id`, `label`). |
| `GET` | `/buckets` | Summary by bucket: counts, sample paths, total size per tier. |
| `GET` | `/config` | Retention rule set (view). |
| `PATCH` | `/config` | Update retention rule set (MVP). |
| `GET` | `/projections` | Objects that will transition in next N days or seconds (`?days=5`, `?seconds=10` in demo). |
| `GET` | `/status` | Component status (client, catcher, buckets, deleted_count). |
| `DELETE` | `/jobs/{id}` | Delete a job (demo). |
| `DELETE` | `/jobs?tag=cache` | Delete jobs by tag (demo: cache/temp files). |
| `POST` | `/demo/reset` | Reset state for demo. |

**Demo mode:** Set `DEMO_MODE=1`; retention uses seconds per package type (e.g. hot 10s, cache 5s→delete). Ingest accepts `tag` (backup|audit|cache) or `package_type`; `X-Demo-Created-Secs-Ago` backdates `created_at`. See `scripts/run-demo.py`.

---

## 4. Data Models (JSON Schemas)

### 4.1 Ingest request (POST /ingest)

```json
{
  "source_id": "string (required)",
  "path": "string (required, logical path relative to source)",
  "checksum": "string (optional, e.g. SHA-256 hex)",
  "size_bytes": "integer (optional)",
  "tier_hint": "string (optional: hot | warm | cold)",
  "tag": "string (optional: backup | audit | cache)",
  "package_type": "string (optional: user_data | app_logs | audit_logs | business_data | job_package | cache)"
}
```

- **Validation:** `source_id` and `path` required; `tier_hint` if present must be one of `hot`, `warm`, `cold`. When `size_bytes` > 0, `checksum` is required (integrity; see §7). **Package type:** When `package_type` is omitted, `tag` is mapped: `backup`→`user_data`, `audit`→`audit_logs`, `cache`→`cache`. Bucket assignment uses the rule set for the package type. **Demo:** `tag=cache` / `package_type=cache` files are eligible for deletion after `cache_seconds`; `X-Demo-Created-Secs-Ago` header backdates `created_at`.

### 4.2 Package (response / GET /packages/{id})

```json
{
  "package_id": "string (alias job_id)",
  "source_id": "string",
  "path": "string",
  "status": "pending | in_progress | completed | failed",
  "progress_percent": 0,
  "checksum": "string (when computed)",
  "bucket": "hot | warm | cold | offsite",
  "created_at": "ISO8601",
  "updated_at": "ISO8601",
  "age_days": 0
}
```

- **progress_percent:** Upload progress (0–100). Updated via PATCH during transfer.
- **checksum:** Included once computed (SHA-256 hex).
- **Deleted:** When data is superseded, delete oldest and keep latest. Messaging in UI.

### 4.4 Bucket summary (GET /buckets)

```json
{
  "buckets": [
    {
      "name": "hot",
      "count": 12,
      "total_bytes": 1024000,
      "sample": [{"job_id": "job-1", "source_id": "s1", "path": "a/b.txt", "age_days": 2}]
    }
  ]
}
```

### 4.5 Config (GET /config, PATCH /config)

```json
{
  "rule_sets": {
    "user_data": {"hot_days": 7, "warm_days": 30, "cold_days": 365, "offsite_days": 2555},
    "app_logs": {"hot_days": 3, "warm_days": 14, "cold_days": 90, "offsite_days": 365},
    "audit_logs": {"hot_days": 0, "warm_days": 7, "cold_days": 365, "offsite_days": 2555},
    "business_data": {"hot_days": 7, "warm_days": 30, "cold_days": 365, "offsite_days": 2555, "replicate_to_all": true},
    "job_package": {"hot_days": 7, "warm_days": 30, "cold_days": 90, "offsite_days": 365},
    "cache": {"cache_seconds": 86400}
  },
  "retention": { "hot_days": 7, "warm_days": 30, "cold_days": 365, "offsite_days": 2555 },
  "demo_mode": false,
  "unit": "days"
}
```

- **Package types:** `user_data`, `app_logs`, `audit_logs`, `business_data`, `job_package`, `cache`. Each type has its own hot/warm/cold/offsite durations. Cache types use `cache_seconds` (delete after N seconds).
- **Replicate:** `replicate_to_all: true` (e.g. for `business_data` like current customer list) replicates data to all storage tiers automatically.
- **PATCH:** Body may include `rule_sets` (e.g. `{"rule_sets": {"user_data": {"hot_days": 14}}}`) or `retention` (legacy, applies to all types). MVP: in-memory update.

### 4.6 Projection (GET /projections?days=5)

```json
{
  "days": 5,
  "transitions": [
    {"bucket_from": "hot", "bucket_to": "warm", "count": 3, "jobs": ["job-1", "job-2", "job-3"]},
    {"bucket_from": "warm", "bucket_to": "cold", "count": 1, "jobs": ["job-4"]}
  ]
}
```

### 4.3 Source (GET/POST /sources)

```json
{
  "source_id": "string",
  "label": "string (optional)",
  "last_seen_at": "ISO8601 (optional)"
}
```

- **Validation:** `source_id` required; `label` optional.

---

## 5. Validation Rules (Lightweight)

- All IDs: non-empty, max 256 chars.
- Timestamps: ISO 8601.
- Enums: `status`, `tier_hint`/`tier` only from allowed sets above.
- No extra required fields beyond those listed; optional fields may be omitted.

---

## 6. Data Classification Framework

| Data class | Examples | Retention | Storage tier | Notes |
|------------|----------|-----------|--------------|-------|
| **Audit** | Ingest events, auth attempts, access, errors | Configurable (see §8) | Cold / immutable | Append-only, tamper-evident. Compliance (SOC 2, PCI-DSS, etc.). |
| **Operational** | Job status, source registry, progress | Configurable | Warm → Cold | Support, troubleshooting, reporting. |
| **Backup payloads** | Actual backup content | Per business policy | Hot → Warm → Cold → Offsite | Lifecycle by tier; see retention presets. |
| **Transient** | In-flight buffers, temp versions, analysis drafts | None | Ephemeral | Not persisted; delete on completion. |

---

## 7. Security & Availability

- **Integrity:** Checksum required on ingest when payload size > 0; verification before promotion to durable storage.
- **Availability:** RTO/RPO targets configurable per tier (e.g., hot: RTO 4h, warm: 24h, cold: 7d). Redundancy options for hot/warm (e.g., replica count).
- **Least privilege:** Auth scopes (later phase); sources restricted to allowed paths.
- **Audit logs:** Append-only, immutable; stored in cold tier. See retention presets (§8).

---

## 8. Data Retention & Lifecycle

All retention values are **configurable**. Catcher exposes defaults via config; override per deployment.

### 8.1 Retention Default Presets

**Preset A — Cloud object storage (S3, GCS, Azure Blob)**

| Data class | Retention | Notes |
|------------|-----------|-------|
| Audit | 1 year | Meets common compliance minimums. |
| Operational metadata | 90 days | Jobs, sources, progress. |
| Backup payloads | Hot 7d → Warm 30d → Cold 1y → Offsite 7y | Lifecycle transitions by age. |

**Preset B — Self-hosted / on-prem (local + NFS + tape)**

| Data class | Retention | Notes |
|------------|-----------|-------|
| Audit | 2 years | Longer when local retention is cheaper. |
| Operational metadata | 180 days | Extended for local forensics. |
| Backup payloads | Hot 14d → Warm 90d → Cold 1y → Offsite 10y | Tape/offsite often cheaper long-term. |

**Preset C — Cost-optimized (cloud with tight budgets)**

| Data class | Retention | Notes |
|------------|-----------|-------|
| Audit | 365 days | Minimum for SOC 2 / typical audits. |
| Operational metadata | 30 days | Minimal for recent troubleshooting. |
| Backup payloads | Hot 3d → Warm 14d → Cold 180d → Offsite 3y | Shorter warm/cold; compress aggressively. |

### 8.2 Configuration Model

Retention is expressed in days (or `null` = retain indefinitely until explicit policy). Example config shape:

```json
{
  "retention": {
    "audit_days": 365,
    "operational_days": 90,
    "backup": {
      "hot_days": 7,
      "warm_days": 30,
      "cold_days": 365,
      "offsite_days": 2555
    }
  }
}
```

Presets are named profiles (e.g. `cloud-object`, `on-prem`, `cost-optimized`) that populate these values; deployments choose a preset and may override individual fields.

### 8.4 Transient Data

In-flight buffers, partial uploads, temporary analysis artifacts: **never persisted**. Delete on job completion or failure handling. No retention configuration.

---

## 9. Cost Optimization

- Audit logs → cold/archive tier; append-only, no updates.
- Operational metadata → warm then cold or delete after retention.
- Backup payloads → lifecycle transitions (hot → warm → cold → offsite) by age/access pattern.
- Transient data → never stored.

---

## 10. Validation & Testing

For each phase and each tool in the toolbox, run validation tests and capture workflow artifacts.

### 10.1 Playwright

- **Tool:** Playwright for E2E and visual capture.
- **Scope:** API health checks; dashboard workflows (load jobs, refresh, view sources); screenshots of key UI states.
- **Artifacts:** Baseline screenshots (e.g. `tests/e2e/snapshots/`), trace files for failures.

### 10.2 Validation Test Sets

| Phase | Tests | Captures |
|-------|-------|----------|
| 1 (Prototype) | Health, ingest, jobs, sources, buckets, config, projections | Dashboard empty; dashboard with jobs; buckets, rule set, projections |
| 2 (MVP) | Windows client ingest; catcher receives | Same + Windows agent status view (if UI) |
| 3 (Extend) | Per-client type (Linux, macOS, NFS) | Multi-source dashboard |
| 4 (Storage) | Tier transitions; retention behavior | Tier labels, retention config UI |

### 10.3 Mock Data for Transfer Validation

Located in `tests/fixtures/mock-data/`. Use for client ingest validation (point `WATCH_DIR` at this path or POST ingest payloads directly).

| File | Path | Size | Notes |
|------|------|------|-------|
| sample.txt | sample.txt | 6 B | Plain text |
| report.json | report.json | 24 B | JSON |
| backup-001.log | data/backup-001.log | 80 B | Nested path |
| empty.bin | empty.bin | 0 B | Zero-byte (checksum optional per §7) |
| config.ini | config.ini | 38 B | Config-style |

Checksums (SHA-256) and `tier_hint` values are in `tests/fixtures/mock-data/MANIFEST.json`.

### 10.4 Validation Steps with Mock Data

1. **Empty state:** Start catcher + dashboard; run Playwright; capture `dashboard-empty.png`.
2. **Seed via API:** POST each mock file from MANIFEST.json to `/api/v1/ingest` (or run client with `WATCH_DIR=tests/fixtures/mock-data`); refresh dashboard.
3. **Transfer visibility:** Verify each `path` appears in Jobs; verify `source_id` in Sources; capture `dashboard-with-jobs.png`.
4. **Integrity:** Confirm ingest accepts only payloads with valid `checksum` when `size_bytes > 0` (reject if checksum missing/wrong).

### 10.5 Workflow Documentation

A README in `tests/` (or `docs/VALIDATION-WORKFLOW.md`) documents:

- How to run the validation suite (e.g. `npm run test:e2e` or `playwright test`).
- Prerequisites (catcher + dashboard running; optional client).
- Mock data location and MANIFEST.json format.
- Workflow steps captured (screenshots with captions).
- Updating baselines (`npx playwright test --update-snapshots`).

---

## 11. Out of Scope (for Initial Spec)

- Authentication/authorization (can be added later).
- Blob upload protocol (e.g. multipart) — Phase 1 can use metadata-only ingest.
- Actual cloud/offsite provider APIs (Phase 4).

---

## 13. Beads Integration

Progress is tracked in Beads. Align tasks with OpenSpec phases:

| Phase | Beads | Commands |
|-------|-------|----------|
| 1 | Prototype tasks (backend, frontend, Docker, validation, mock data) | `bd ready` → implement → `bd close <id>` |
| 2 | Windows agent, package | P2 blocked until P1 complete |
| 3 | Linux/macOS, NFS | P3 blocked until P2 complete |
| 4 | Cloud tiers, offsite | P4 blocked until P3 complete |

Seed: `./scripts/beads-setup.sh`. Sync: `bd sync`.

---

*Keep this spec updated as the design evolves; propose changes here first, then implement, then update Beads.*
