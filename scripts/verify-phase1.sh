#!/usr/bin/env bash
# Verify Phase 1: Playwright e2e (auto-starts backend + frontend via playwright.config.js).
set -e
cd "$(dirname "$0")/.."

echo "=== Phase 1 Verification (Playwright) ==="
npm run test:e2e
echo ""
echo "=== Beads Phase 1 (closed) ==="
bd list --status closed 2>/dev/null | head -20 || true
echo ""
echo "Run 'bd sync' and commit .beads/issues.jsonl to persist Beads updates."
