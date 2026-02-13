#!/usr/bin/env bash
# Verify Phase 1: run Playwright tests. Assumes backend (8000) and frontend (5173) are running.
# Start with: npm run serve
set -e
cd "$(dirname "$0")/.."

echo "=== Phase 1 Verification ==="
npm run test:e2e
echo ""
echo "=== Beads Phase 1 (closed) ==="
bd list --status closed 2>/dev/null | head -20 || true
echo ""
echo "Run 'bd sync' and commit .beads/issues.jsonl to persist Beads updates."
