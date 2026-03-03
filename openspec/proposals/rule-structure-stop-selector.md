# Proposal: Rule Structure — Stop Selector + Wait Time

## Summary

Retention rules use a **stops** format where each package type explicitly defines:
1. **Stop selector** — whether the package stops at each stop (hot, warm, cold, offsite)
2. **Wait time** — how long the package stays at each stop (minimum 1 when enabled)
3. **Offsite:** max `wait_days` or `never_delete: true` for indefinite retention

**Implemented.** No backward compatibility with legacy `hot_days` / `warm_days` format.

---

## Model: Stops + Wait Time

### Structure

Each package type has a `stops` object. For each stop name (`hot`, `warm`, `cold`, `offsite`):
- **`enabled`** (boolean) — does the package stop here?
- **`wait_days`** / **`wait_seconds`** — duration at stop; **minimum 1 when enabled**
- **Offsite only:** **`never_delete`** (boolean) — `true` = retain indefinitely; `false` + `wait_days` = max retention

```json
{
  "rule_sets": {
    "user_data": {
      "stops": {
        "hot":    { "enabled": true,  "wait_days": 7 },
        "warm":   { "enabled": true,  "wait_days": 30 },
        "cold":   { "enabled": true,  "wait_days": 365 },
        "offsite": { "enabled": true, "wait_days": 2555, "never_delete": false }
      }
    },
    "audit_logs": {
      "stops": {
        "hot":    { "enabled": false },
        "warm":   { "enabled": true,  "wait_days": 7 },
        "cold":   { "enabled": true,  "wait_days": 365 },
        "offsite": { "enabled": true, "never_delete": true }
      }
    }
  }
}
```

### Defaults & Validation

- **`enabled`**: default `true` if omitted
- **`wait_days`** / **`wait_seconds`**: default 7 when enabled and not specified
- **Strict order:** earlier tier must be enabled before later (e.g. warm enabled requires hot enabled)
- **Minimum wait:** enabled stops require wait ≥ 1

### Boundary Computation

For a package type, compute cumulative age boundaries (hot → warm → cold). Offsite starts after cold_end; retention there uses `never_delete` or `wait_days`.

### Demo Mode

Same structure with `wait_seconds` instead of `wait_days`:

```json
{
  "stops": {
    "hot":   { "enabled": true,  "wait_seconds": 10 },
    "warm":  { "enabled": true,  "wait_seconds": 30 },
    ...
  }
}
```

Default `wait_seconds`: 7 when in demo mode (or keep 10 for hot in demo walkthrough).

---

## Special Cases

### Cache

Cache uses `cache_seconds` and does not use stops:

```json
{
  "cache": {
    "cache_seconds": 86400
  }
}
```

No `stops`; package is deleted after `cache_seconds`. Existing behavior unchanged.

### Replicate (business_data)

```json
{
  "business_data": {
    "stops": { ... },
    "replicate_to_all": true
  }
}
```

Replicate remains a separate flag.

---

## API Shape (GET /config)

### Response

```json
{
  "rule_sets": {
    "user_data": {
      "stops": {
        "hot":    { "enabled": true,  "wait_days": 7 },
        "warm":   { "enabled": true,  "wait_days": 30 },
        "cold":   { "enabled": true,  "wait_days": 365 },
        "offsite": { "enabled": true, "wait_days": 2555 }
      }
    }
  },
  "demo_mode": false,
  "unit": "days"
}
```

### PATCH /config

Accept `rule_sets` with full `stops` per package type. Validation: strict order, min wait ≥ 1, offsite supports `never_delete`.

---

## Implementation Checklist

| Area | Status |
|------|--------|
| **Backend** | ✅ `_stops_to_boundaries()`, `_validate_stops()`, stops format only |
| **OpenSpec** | ✅ §4.5 Config and §8 updated |
| **Frontend** | ✅ Rules/Train Lines use stops; offsite ∞ display |
| **Text UI** | ✅ Displays stops + never_delete as ∞ |

---

## Resolved

- **Offsite:** `never_delete: true` = indefinite; `never_delete: false` + `wait_days` = max retention
- **Validation:** `enabled: true` requires wait ≥ 1
- **Order:** Strict (hot → warm → cold → offsite); earlier tier must be enabled before later
