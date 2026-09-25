# bookish-train (Edge Backup System)

Tracks backup job metadata from edge clients to storage tiers (Catcher FastAPI + Svelte dashboard + Text UI). Does not store payload bytes.

Stack: Python/FastAPI backend, Svelte frontend, SQLite (TrueNAS path), Docker clients, restic/rclone prototypes.
Posture: ponytail (repo >30 days). Shared health pack in `.cursor/skills/` and `.cursor/rules/`.

## Commands

- Backend: `cd backend && pip install -r requirements.txt && uvicorn main:app --port 8000`
- Frontend: `cd frontend && npm install && npm run dev` (http://localhost:5173)
- Text UI: `python scripts/text-ui.py` or `--live`
- Seed demo: `python scripts/seed-demo-data.py`
- Containers: `./scripts/up.sh`
- E2E: `npm run test:e2e` or `npm run verify`
- Beads: `bd ready` → work → `bd close <id>` → `bd export -o .beads/issues.jsonl`

## Hard prohibitions

- Do not move or store payload bytes in the Catcher. Engines (clients) copy data; dispatcher tracks manifests only.
- Do not invent API routes, package types, or env vars not in OpenSpec / `.env.example`.
- Do not rewrite OpenSpec or Gherkin to match a hoped-for future. Update only when code already changed.
- Do not skip `bd export` / push at session end if Beads work was done.

## Verify by change type

| Change | Check |
| --- | --- |
| UI / Svelte | `cd frontend && npm run dev` + dashboard data-flow / empty screens |
| API / FastAPI | curl or test against `/api/v1/ingest`, `/packages`, `/status` |
| Spec | matching `features/*.feature` + `openspec/specs/edge-backup-system.md` still true |
| Client / scripts | run seed or restic-rclone-backup mock; Text UI shows progress |
| Deploy / TrueNAS | follow `docs/TRUENAS-DEPLOYMENT.md`; no assumed public Vercel |

## Source of truth

- Behavior: `openspec/specs/edge-backup-system.md` + `features/*.feature`
- Remaining work: Beads (`.beads/`) / GitHub issues
- Railway model & resume: `docs/RAILWAY-ARCHITECTURE.md`
- Health bar: `.cursor/rules/repo-health.mdc` (do not duplicate)

## House vocabulary

- **Catcher / Dispatcher** — control-plane API (not a storage service).
- **Engine** — edge client that moves data.
- **Railcar / Package** — unit of tracked backup data.
- **Station / yard** — actual storage (TrueNAS, S3, restic repo).
- **Signal board** — web dashboard or Text UI.
- Prefer railway terms over generic “job/server” when describing architecture.

## Good / bad

Bad: Putting payload bytes or restic repo logic inside `backend/main.py`.
Good: Client scripts POST/PATCH metadata only; storage stays on engines/stations.

## Borrowed patterns

- Hard prohibitions, verification-matrix, single-source, house-vocabulary from ossrules.md (Airflow / VoiceStudio-style patterns).
