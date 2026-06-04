# Bookish Train — Share-Ready Plan

Edge Backup Railway (“bookish train”) is a Phase 1 prototype: metadata flows from edge clients into the **Catcher**, retention **rules** assign tiers (hot → warm → cold → offsite), and the **dashboard** visualizes the train.

This document records gaps found before sharing with friends and the fixes applied on branch `cursor/share-ready-9a5a`.

## Missing information (identified)

| Gap | Impact | Resolution |
|-----|--------|------------|
| No friend-facing quickstart | Friends don’t know Node/Python/Podman versions or order of steps | `docs/FRIEND-QUICKSTART.md` |
| No `.env.example` | Env vars scattered across compose and scripts | `.env.example` at repo root |
| `npm run serve` / `npm run backend` broken | `scripts/start-backend.js` missing | Added `scripts/start-backend.js` wrapping `run-backend.sh` |
| Empty `clients/docker-client/test-data/` | Container clients ingest nothing | Compose mounts `tests/fixtures/mock-data`; `scripts/sync-test-data.sh` for local copy |
| README images missing | Broken hero and screenshot links on GitHub | Run `npm run capture-screenshots`; README notes optional `cartoon.jpg` |
| Preset API without UI | Can’t try cloud/onprem/cost scenarios from dashboard | Settings → Scenario preset apply |
| In-memory Catcher | Restart clears data | Documented in quickstart |
| No CI | Regressions only caught locally | `npm run verify` documents local gate; CI optional later |
| Unpushed restic commit | Clone from GitHub missing MinIO/restic | Push branch + PR |

## Design updates (share scope)

1. **Demo paths** — Three tiers, documented in FRIEND-QUICKSTART:
   - **Fastest:** `./scripts/up.sh` + open dashboard + `python scripts/seed-demo-data.py`
   - **Animated:** `DEMO_MODE=1` + `python scripts/run-demo.py` (2-minute timeline)
   - **Real backup:** compose stack with `restic-client` + MinIO

2. **Settings: scenario presets** — Apply `cloud`, `onprem`, or `cost` rule sets via PATCH `/config` (OpenSpec §8.1).

3. **Validation gate** — `npm run verify` = checksum smoke + Playwright e2e (auto-starts backend/frontend).

## Out of scope (Phase 2+)

- Auth, persistence, real tier execution, Windows agent, dynamic package types (Beads tasks open).

## Verification checklist

```bash
./scripts/verify.sh              # backend validation + compose config
npm run verify                   # verify.sh + test:e2e
npm run capture-screenshots      # refresh docs/*.png from Playwright
python scripts/seed-demo-data.py # populate dashboard
```

## Files touched (this effort)

- `docs/FRIEND-QUICKSTART.md`, `docs/SHARE-PLAN.md`, `.env.example`
- `scripts/start-backend.js`, `scripts/sync-test-data.sh`, `scripts/up.sh`
- `docker-compose.yml`, `docker-compose.phase1-assess.yml`
- `package.json`, `scripts/verify-phase1.sh`
- `frontend/src/stores/config.svelte.js`, `frontend/src/App.svelte`
- `README.md`

---

<!-- /autoplan restore point: autoplan review 2026-06-01 -->

## GSTACK REVIEW REPORT (/autoplan)

**Branch:** `cursor/share-ready-9a5a` | **Base:** `origin/main` | **Verdict:** APPROVED (auto, P6 bias toward action)

### CEO (SELECTIVE EXPANSION)

| Finding | Decision |
|---------|----------|
| Right problem: friends can't run the demo | Accept — quickstart + fixed `npm run serve` is the wedge |
| Scope includes restic + presets + docs + e2e | Accept — all in blast radius for share-ready |
| CI deferred | Defer to Beads/TODOS — `npm run verify` is local gate for now |
| Main diverged (railway MVP, observability) | Rebase/merge before land — done in this session |

**NOT in scope:** auth, persistence, GitHub Actions CI, demo-mode preset unit translation.

### Design (7 dimensions, UI scope)

| Dimension | Score | Notes |
|-----------|-------|-------|
| Information hierarchy | 8/10 | SPA nav clear; FRIEND-QUICKSTART points to Tracks first |
| Empty/error states | 7/10 | Documented in quickstart; demo seed in Settings |
| Preset UX | 8/10 | Settings placement correct; demo-mode warning present |
| Share polish | 7/10 | Screenshots refreshed; hero cartoon still optional |

### Eng

```
[Browser] → npm run serve / ./scripts/up.sh
    → frontend (Vite) + backend (uvicorn)
    → PATCH /config (presets) ← config.svelte.js
    → Playwright e2e (17 tests)
```

| Check | Status |
|-------|--------|
| Architecture | OK — thin wrappers, fixture mount, no new infra |
| Tests | OK — e2e updated for SPA; preset asserts onprem wait_days=14 |
| Security | Phase-1 acceptable — no auth by design; MinIO demo creds documented |
| Ship blockers | None |

### Decision Audit Trail

| # | Phase | Decision | Principle | Rationale |
|---|-------|----------|-----------|-----------|
| 1 | CEO | Merge with origin/main before land | P6 | Main advanced; avoid fork drift |
| 2 | Eng | Strengthen preset e2e (onprem/14d) | P1 | Prove PATCH works, not just UI click |
| 3 | CEO | Defer CI | P3 | Local verify passes; CI is ocean not lake |
| 4 | Design | Keep preset UI in Settings | P5 | Explicit, matches OpenSpec §8.1 |

### Cross-phase theme

**Demo honesty:** CEO + Eng both flag metadata-only vs "real backup" narrative — quickstart caveats address this; restic stack optional path included.

**STATUS:** DONE — `npm run verify` 17/17 pass after merge.
