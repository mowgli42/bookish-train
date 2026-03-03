# Plan Review: Extended Rules for Alternate Data Types & Scenario Presets

**Scope chosen:** 1C — SMALL CHANGE (compressed review)

**Implemented:** Per-rule descriptions (§4.5.1), per-scenario summaries + preset→rule_sets mapping (§8.1), ASCII diagram.

---

## Compressed Review — Single Pass

### Issue 1 (Architecture): Preset values diverge from backend defaults

**Problem:** §8.1 Preset C defines `app_logs: 1d/7d/90d/1y` and `cache: 3600s`. Backend `_default_stops_days()` has `app_logs: 3/14/90/365` and `cache: 86400`. The spec now documents scenario-specific values that the implementation does not ship. Deployments applying "Preset C" would need to PATCH config; there is no "load preset" API.

**Options:**
- **A)** Keep spec as design-only; backend keeps current defaults; deployments manually PATCH to match a preset. (Effort: none. Risk: low. Maintenance: spec and code can drift.)
- **B)** Add backend constants for each preset (e.g. `PRESET_CLOUD`, `PRESET_ONPREM`, `PRESET_COST`) and align §8.1 to those. (Effort: low. Risk: low. Maintenance: single source of truth.)
- **C)** Add `GET /config/presets` and `POST /config/apply-preset?preset=A` API. (Effort: medium. Risk: medium. Maintenance: API + spec.)

**Recommendation:** A. Spec is documentation; implementation can follow later. Explicit over clever — no hidden magic.

---

### Issue 2 (Code Quality): Data class vs package type naming

**Problem:** §6 uses "Audit", "Operational", "Backup payloads"; §4.5/§8 use `audit_logs`, `app_logs`, `user_data`. The mapping is implicit. A reader might not connect "Operational metadata" → `app_logs` + `job_package`.

**Options:**
- **A)** Add a one-line mapping in §6 or §8: "Audit ↔ audit_logs; Operational ↔ app_logs, job_package; Backup ↔ user_data, business_data." (Effort: trivial. Risk: none. Maintenance: none.)
- **B)** Leave as-is; mapping is inferable from context. (Effort: none. Risk: minor confusion.)
- **C)** Rename package types to match data classes. (Effort: high. Risk: breaking change. Maintenance: high.)

**Recommendation:** A. Minimal diff; explicit over clever.

---

### Issue 3 (Tests): No automated validation of preset→rule_sets consistency

**Problem:** Presets in §8.1 are prose + tables. If someone edits the spec or backend defaults, there is no test to catch drift.

**Test diagram:**

```
┌──────────────────────────────────────────────────────────────────────────┐
│  TEST COVERAGE FOR RULES + PRESETS                                        │
└──────────────────────────────────────────────────────────────────────────┘

  [E2E: GET /config]
       │
       ├──► rule_sets has expected keys (user_data, audit_logs, ...)
       │
       ├──► user_data.stops matches expected shape (hot, warm, cold, offsite)
       │
       └──► (NEW) Optional: fixture with preset A/B/C rule_sets; assert structure

  [Spec / docs]
       │
       └──► (NEW) Optional: script or test that parses §8.1 tables and validates
            JSON structure (e.g. all package types present, stops have 4 keys)
```

**Options:**
- **A)** Add E2E assertion that config returns all 6 package types with valid stops/cache shape. (Effort: low. Risk: none. Maintenance: low.)
- **B)** Add a test that loads a JSON fixture per preset and validates structure. (Effort: medium. Risk: none. Maintenance: fixtures must match spec.)
- **C)** No new tests; spec-only change. (Effort: none. Risk: drift undetected.)

**Recommendation:** A. Well-tested code is non-negotiable; minimal addition.

---

### Issue 4 (Performance): N/A

**Finding:** Spec-only change. No runtime impact. No N+1, memory, or caching concerns.

---

## NOT in scope

| Item | Rationale |
|------|-----------|
| Preset API (GET/apply) | Deferred until spec is stable and product need is clear |
| UI preset selector | Deferred; spec documents design only |
| New package types | Current 6 cover scenarios; extensibility via rules-flexibility proposal |
| Backend preset constants | Deferred; backend keeps current defaults |
| Beads issues for preset API | Deferred |

---

## What already exists

| Item | Reused? |
|------|---------|
| §8.1 Presets A/B/C (data class view) | Yes — extended with package-type mapping and scenario summaries |
| §4.5 Config, rule_sets structure | Yes — added §4.5.1 per-rule descriptions |
| §6 Data classification | Yes — linked implicitly; Issue 2 suggests explicit mapping |
| Backend `_default_stops_days()` | Yes — spec documents design; backend unchanged |

---

## Failure modes

| Codepath | Failure scenario | Test? | Error handling? | User sees? |
|----------|------------------|-------|-----------------|------------|
| Spec §8.1 tables | Editor typos (wrong days, wrong package type) | No (Issue 3A would add config shape test) | N/A | Silent doc error |
| Preset application (future) | User selects preset; PATCH fails | N/A (not implemented) | N/A | N/A |

**Critical gap:** None for spec-only change. If preset API is added later, failure modes must be re-evaluated.

---

## Completion summary

- **Step 0:** User chose 1C (compressed review)
- **Architecture:** 1 issue (preset vs backend defaults)
- **Code Quality:** 1 issue (data class ↔ package type mapping)
- **Test:** 1 issue + diagram; 1 gap (config shape assertion)
- **Performance:** 0 issues (N/A)
- **NOT in scope:** Written
- **What already exists:** Written
- **TODOS.md updates:** 0 (deferred items captured in NOT in scope)
- **Failure modes:** 0 critical gaps

---

## Resolved decisions

1. **Issue 1:** 1B — Backend preset constants added (`PRESET_CLOUD`, `PRESET_ONPREM`, `PRESET_COST`); `GET /config/presets` exposes them; default = Cloud.
2. **Issue 2:** 2A — Explicit data class ↔ package type mapping in §6.
3. **Issue 3:** 3A — E2E config shape assertion added; all 6 package types validated; presets endpoint test added.
