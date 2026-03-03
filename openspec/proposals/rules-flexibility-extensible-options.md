# Proposal: Rules Flexibility — Extensible Rules + Universal Options

## Summary

1. **Add new rules** — Support dynamic package types (not a fixed enum); users can create custom rules.
2. **Universal options** — Every rule can have `cache_seconds` and `replicate_to_all`, not just cache and business_data.

---

## Current Limitations

- **Fixed package types:** `user_data`, `app_logs`, `audit_logs`, `business_data`, `job_package`, `cache` — hardcoded.
- **cache_seconds** — Only on `cache`; other rules cannot use it.
- **replicate_to_all** — Only on `business_data`; other rules cannot replicate.

---

## Target Model

### Rule structure (per rule)

Each rule is an object with **optional** fields:

| Field | Type | Meaning |
|-------|------|---------|
| `stops` | object | Tier flow: hot → warm → cold → offsite. Omit = no tier flow. |
| `cache_seconds` | number | Time in hot storage before delete. Omit or 0 = no cache behavior. |
| `replicate_to_all` | boolean | Copy to all tiers. Default false. |

### Semantics

- **Cache-only rule:** `cache_seconds` set, no `stops` → stays in hot for N seconds, then deleted.
- **Tier rule:** `stops` set, no `cache_seconds` → flows through hot/warm/cold/offsite per stops.
- **Cache + tier:** `cache_seconds` + `stops` both set → stays in hot for at least `cache_seconds`, then flows per stops. (Phase 2; prototype may keep them mutually exclusive.)
- **Replicate:** `replicate_to_all: true` → replicate to all tiers (applies when `stops` present).

**Prototype scope:** Cache and stops mutually exclusive. Replicate available for any rule with stops. **UI:** gray out non-selectable options (e.g. when cache mode is on, gray out stops; when stops mode is on, gray out cache).

---

## Adding New Rules

### Backend

- Remove hardcoded `PACKAGE_TYPES` for validation; accept any string as package_type.
- PATCH /config can add a new rule: `{ "rule_sets": { "my_custom_type": { "stops": {...} } } }`.
- GET /config returns all rule_sets; no fixed list.
- Ingest: `package_type` accepts any value present in rule_sets. **Default to `user_data`** if omitted or unknown.

### Frontend

- Rules grid displays all rule_sets from config (already dynamic).
- Edit form: dropdown includes all existing types.
- **Add rule** button: opens form to create a new rule (name + options). Submits PATCH with new entry.

### Delete rule

- PATCH with `{ "package_type": null }` or DELETE rule? Or omit from rule_sets?
- Simplest: PATCH sends full rule_sets; to delete, client omits that key. Backend would need a "replace all" or "delete rule" API.
- Alternative: `PATCH /config` with `rule_sets: { "to_delete": null }` to remove.

---

## Universal Options

### cache_seconds

- **When used alone:** Rule is cache-type; kept in hot for N seconds, then deleted.
- **Availability:** Any rule. Today only `cache` has it.

### replicate_to_all

- **When used:** With `stops`; replicates packages to all tiers.
- **Availability:** Any rule. Today only `business_data` has it.

### Edit form changes

- Show `cache_seconds` toggle/input for every rule.
- Show `replicate_to_all` checkbox for every rule (when stops present).
- Rule can be: cache-only, tier-only, or (later) both.

---

## Implementation Phases

### Phase 1: Universal options (minimal)

- [ ] Backend: Allow `cache_seconds` and `replicate_to_all` on any rule. Validate accordingly.
- [ ] Frontend: Edit form shows cache_seconds and replicate for all rules, not just cache/business_data.
- [ ] No API change; just relax validation and extend UI.

### Phase 2: Dynamic rules (add new)

- [ ] Backend: Accept any package_type string in rule_sets; remove or soften PACKAGE_TYPES restriction.
- [ ] Backend: Ingest accepts any package_type that exists in rule_sets.
- [ ] Frontend: "Add rule" button + form; name + options.
- [ ] Frontend: Edit dropdown + grid already dynamic.

### Phase 3: Delete rules

- [ ] Define delete semantics (PATCH with null, or separate DELETE).
- [ ] Handle packages that reference deleted rule (fallback to user_data?).

---

## API Shape (Phase 1–2)

### PATCH /config

```json
{
  "rule_sets": {
    "user_data": {
      "stops": { "hot": {...}, "warm": {...}, "cold": {...}, "offsite": {...} },
      "cache_seconds": null,
      "replicate_to_all": false
    },
    "my_custom": {
      "stops": { ... },
      "replicate_to_all": true
    },
    "ephemeral_cache": {
      "cache_seconds": 3600
    }
  }
}
```

### Validation

- Rule must have either `stops` or `cache_seconds` (or both in Phase 2).
- If `stops`: full stops validation (order, min wait, etc.).
- If `cache_seconds`: number ≥ 1.
- `replicate_to_all`: only meaningful when `stops` present.

---

## Resolved

1. **Cache + stops:** Mutually exclusive. Use **display logic** — gray out non-selectable items (e.g. cache mode on → gray out stops; stops mode on → gray out cache).
2. **Unknown/missing package_type:** Default to **user_data**.
3. **Rule naming:** Restrict to **common format**: lowercase letters, digits, underscores (e.g. `^[a-z][a-z0-9_]*$`).
