#!/usr/bin/env bash
# Seed Beads with OpenSpec-aligned tasks.
# Run from repo root. Requires: bd (Beads CLI)
set -e
cd "$(dirname "$0")/.."

if ! command -v bd &>/dev/null; then
  echo "Beads (bd) is not installed. Install first, e.g.:"
  echo "  brew install beads   # macOS/Linux"
  echo "  go install github.com/steveyegge/beads/cmd/bd@latest"
  echo ""
  echo "Until then, track progress in docs/TASKS.md"
  exit 1
fi

bd init --quiet 2>/dev/null || true

# Phase 1
bd create "P1: Init catcher backend (FastAPI)" -t task -p 1
bd create "P1: Define API routes (ingest, jobs, sources)" -t task -p 1
bd create "P1: Checksum required when size_bytes > 0" -t task -p 1
bd create "P1: Init frontend (Svelte) and dashboard" -t task -p 1
bd create "P1: Dashboard sources list view" -t task -p 1
bd create "P1: Dashboard IxDF signifiers and feedback" -t task -p 1
bd create "P1: Docker Compose (catcher + client + dashboard)" -t task -p 1
bd create "P1: Client script in container (watch, POST /ingest)" -t task -p 1
bd create "P1: Playwright validation (health, dashboard, sources)" -t task -p 1
bd create "P1: Mock data for transfer validation (MANIFEST.json, fixtures)" -t task -p 1
bd create "P1: Fix Svelte \$state rune (.svelte.js stores)" -t task -p 1

# Text UI (P1 parallel — alternative to web dashboard)
bd create "P1: Text UI — one-shot status report (component status, buckets)" -t task -p 1
bd create "P1: Text UI — packages, clients, rules, projections" -t task -p 1
bd create "P1: Text UI — live refresh mode (--live, CATCHER_URL)" -t task -p 1

# Phase 2
bd create "P2: Windows endpoint agent (monitor local folders)" -t task -p 2
bd create "P2: Package Windows tooling for deployment" -t task -p 2

# Phase 3 & 4
bd create "P3: Linux/macOS clients and network filesystems" -t task -p 3
bd create "P4: Cloud storage tiers (hot/warm/cold) and offsite" -t task -p 3

# Dependencies: P2 agent -> P1 client; P2 package -> P2 agent; P3 -> P2; P4 -> P3
# Run manually after first seed: bd dep add <blocked> <blocker>
# e.g. bd dep add <P2-agent-id> <P1-client-id>

echo "Beads tasks created. Run: bd ready"
bd ready
