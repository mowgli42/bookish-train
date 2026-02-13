# Validation Tests

E2E and visual tests for the Edge Backup System. Uses **Playwright** to capture web displays and validate workflows per phase.

## Quick run

```bash
# From repo root; ensure catcher (:8000) and dashboard (:5173) are running
npm install
npm run test:e2e
```

## Documentation

→ [docs/VALIDATION-WORKFLOW.md](../docs/VALIDATION-WORKFLOW.md) — prerequisites, commands, per-phase test matrix, workflow steps with screenshots.

## Structure

```
tests/
├── README.md
├── fixtures/
│   └── mock-data/          # Mock files for transfer validation
│       ├── MANIFEST.json   # path, size_bytes, checksum, tier_hint per file
│       ├── sample.txt
│       ├── report.json
│       ├── data/backup-001.log
│       ├── empty.bin
│       └── config.ini
├── e2e/
│   ├── dashboard.spec.js   # Phase 1: health, dashboard, affordances, integrity
│   ├── snapshots/          # Baseline screenshots (created on first run)
│   └── test-results/       # Run artifacts
```

## Per-phase coverage

| Phase | Spec | Captures |
|-------|------|----------|
| 1 | `dashboard.spec.js` | Dashboard empty state |
| 2+ | To be added | Dashboard with jobs; per-client flows |
