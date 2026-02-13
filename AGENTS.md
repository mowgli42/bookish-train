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
- **End of session:** Run `bd sync` so the JSONL store is written and can be committed. This keeps task state in git and restores context in the next session.

**Dependencies**

- Add a dependency (B blocks A): `bd dep add B A` → B depends on A (B is blocked until A is done).
- Inspect: `bd dep tree <id>`, `bd blocked`, `bd ready`.

**Summary for the agent**

1. Run `bd ready` at session start.
2. Implement only unblocked tasks; close tasks when done with `bd close <id>`.
3. Create new issues for discovered work; use `bd dep add` to keep the graph consistent.
4. Run `bd sync` before ending the session.

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
3. **Track** in Beads: close completed tasks, add new ones, keep dependencies correct; use `bd ready` and `bd sync`.

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
   bd sync
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
