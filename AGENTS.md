# Agent instructions: Beads and OpenSpec workflow

This project uses **OpenSpec** as the single source of truth for the system and **Beads** for dependency-aware task tracking and session memory. Follow this workflow when implementing or extending the edge backup system.

---

## Beads: session memory and task management

- **Always prefer `bd` for programmatic use:** use `--json` when you need to parse output (e.g. `bd list --json`, `bd show <id> --json`).
- **Start of session:** Run `bd ready` to see unblocked work. Optionally run `bd prime` if the project has Beads hooks set up (e.g. `bd setup cursor`), which injects a short workflow summary.
- **Choosing work:** Pick tasks from `bd ready`. Do not start work that is blocked by incomplete dependencies; resolve blockers first or pick another ready task.
- **During implementation:** When you discover new work (e.g. a bug or follow-up), create a Beads issue and link it:
  ```bash
  bd create "Short title" --description "Details..." --deps discovered-from:bd-<parent-id> --json
  ```
- **After completing a task:** Mark it closed: `bd close <id>`. Then run `bd ready` again to get the next unblocked set.
- **End of session:** Run `bd export -o .beads/issues.jsonl` so the tracked JSONL store is written and can be committed. This keeps task state in git and restores context in the next session.

**Dependencies**

- Add a dependency (B blocks A): `bd dep add B A` → B depends on A (B is blocked until A is done).
- Inspect: `bd dep tree <id>`, `bd blocked`, `bd ready`.

**Summary for the agent**

1. Run `bd ready` at session start.
2. Implement only unblocked tasks; close tasks when done with `bd close <id>`.
3. Create new issues for discovered work; use `bd dep add` to keep the graph consistent.
4. Run `bd export -o .beads/issues.jsonl` before ending the session.

---

## OpenSpec: spec-first changes

- **Spec location:** `openspec/specs/edge-backup-system.md` defines architecture, phases, API endpoints, JSON request/response models, and validation rules.
- **Before implementing a feature:** Propose changes in the spec (or in a new spec under `openspec/specs/` if it’s a separate capability). Describe new endpoints, request/response shapes, and validation. Keep the spec lightweight; avoid over-specifying.
- **After updating the spec:** Implement code and tests to match. Then update Beads: close the corresponding task(s) or add new tasks and dependencies as needed.
- **If using OpenSpec slash commands:** Use `/opsx:new <change-name>` to create a change folder, `/opsx:ff` to generate proposal/specs/design/tasks, `/opsx:apply` to implement, and `/opsx:archive` when done. The existing `edge-backup-system.md` can be referenced or updated from those artifacts.

---

## Workflow summary

1. **Propose** in OpenSpec (edit `openspec/specs/edge-backup-system.md` or create a change).
2. **Apply** in code (backend, frontend, or client scripts).
3. **Track** in Beads: close completed tasks, add new ones, keep dependencies correct; use `bd ready` and `bd export -o .beads/issues.jsonl`.

This keeps the system aligned with the spec and gives the next session (or another agent) a clear view of what’s done and what’s ready to do.

## Landing the Plane (Session Completion)

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   bd export -o .beads/issues.jsonl
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds

---

## Cursor Cloud specific instructions

### Services overview

| Service | Command | Port |
|---------|---------|------|
| **Backend (Catcher)** | `cd backend && ../backend/.venv/bin/python -m uvicorn main:app --port 8000 --host 127.0.0.1` | 8000 |
| **Frontend (Svelte/Vite)** | `cd frontend && npm run dev -- --host 127.0.0.1` | 5173 |

The backend is purely in-memory (no DB). The frontend proxies `/api` to the backend via Vite config.

### Running services

- Start backend first, then frontend. The Playwright config auto-starts both via `webServer` entries if they aren't already running.
- The Playwright `webServer` for the backend expects the venv at `backend/.venv/` (see `playwright.config.js`).
- Use `npm run serve` from root to start both concurrently (backend + frontend).

### Testing

- **E2E tests:** `npm run test:e2e` — Playwright tests (8/14 currently pass; 6 UI tests fail due to pre-existing heading mismatch: tests expect "Edge Backup Dashboard" but UI says "Edge Backup Railway").
- **Scenario test (API only):** `npx playwright test phase1-scenario` — passes; validates full ingest → packages → buckets → sources → config → projections workflow.
- **Build check:** `cd frontend && npx vite build` — verifies the frontend compiles.
- The `scripts/tools/` directory referenced in docs does not exist; `scripts/phase1-scenario.sh` fails because of this. Use the Playwright scenario test instead.

### Gotchas

- `python3.12-venv` apt package must be installed before creating the venv (not present by default in the VM image).
- The `@svar-ui/svelte-grid` package used by the frontend reports a few a11y warnings during build — these are pre-existing and not blocking.
- No linter is configured in this repo (no ESLint, Ruff, etc.). `vite build` serves as the primary static analysis check.
