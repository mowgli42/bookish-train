"""
Catcher service: ingest API and job/source tracking.
See openspec/specs/edge-backup-system.md for API and data models.
Demo mode: DEMO_MODE=1 uses retention in seconds for 2-min walkthrough.
"""
import copy
import json
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Literal

from fastapi import FastAPI, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, model_validator

DEMO_MODE = os.environ.get("DEMO_MODE", "").lower() in ("1", "true", "yes")

app = FastAPI(title="Edge Backup Catcher", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# In-memory store (replace with DB in later phases)
JOBS: dict[str, dict] = {}
SOURCES: dict[str, dict] = {}
DELETED_COUNT = 0  # For demo: count of deleted cache items
_JOB_ID = 0

PACKAGE_TYPES = ("user_data", "app_logs", "audit_logs", "business_data", "job_package", "cache")
BUCKETS_ORDER = ("hot", "warm", "cold", "offsite")

# Default wait when enabled and not specified
DEFAULT_WAIT_DAYS = 7
DEFAULT_WAIT_SECONDS = 7

# Rule sets: stops format. Each stop has enabled, wait_days/wait_seconds; offsite has optional never_delete.
def _default_stops_days() -> dict:
    return {
        "user_data": {
            "stops": {
                "hot": {"enabled": True, "wait_days": 7},
                "warm": {"enabled": True, "wait_days": 30},
                "cold": {"enabled": True, "wait_days": 365},
                "offsite": {"enabled": True, "wait_days": 2555, "never_delete": False},
            }
        },
        "app_logs": {
            "stops": {
                "hot": {"enabled": True, "wait_days": 3},
                "warm": {"enabled": True, "wait_days": 14},
                "cold": {"enabled": True, "wait_days": 90},
                "offsite": {"enabled": True, "wait_days": 365, "never_delete": False},
            }
        },
        "audit_logs": {
            "stops": {
                "hot": {"enabled": False},
                "warm": {"enabled": True, "wait_days": 7},
                "cold": {"enabled": True, "wait_days": 365},
                "offsite": {"enabled": True, "never_delete": True},
            }
        },
        "business_data": {
            "stops": {
                "hot": {"enabled": True, "wait_days": 7},
                "warm": {"enabled": True, "wait_days": 30},
                "cold": {"enabled": True, "wait_days": 365},
                "offsite": {"enabled": True, "wait_days": 2555, "never_delete": False},
            },
            "replicate_to_all": True,
        },
        "job_package": {
            "stops": {
                "hot": {"enabled": True, "wait_days": 7},
                "warm": {"enabled": True, "wait_days": 30},
                "cold": {"enabled": True, "wait_days": 90},
                "offsite": {"enabled": True, "wait_days": 365, "never_delete": False},
            }
        },
        "cache": {"cache_seconds": 86400},
    }


def _default_stops_seconds() -> dict:
    return {
        "user_data": {
            "stops": {
                "hot": {"enabled": True, "wait_seconds": 10},
                "warm": {"enabled": True, "wait_seconds": 30},
                "cold": {"enabled": True, "wait_seconds": 60},
                "offsite": {"enabled": True, "wait_seconds": 90, "never_delete": False},
            }
        },
        "app_logs": {
            "stops": {
                "hot": {"enabled": True, "wait_seconds": 5},
                "warm": {"enabled": True, "wait_seconds": 15},
                "cold": {"enabled": True, "wait_seconds": 45},
                "offsite": {"enabled": True, "wait_seconds": 60, "never_delete": False},
            }
        },
        "audit_logs": {
            "stops": {
                "hot": {"enabled": False},
                "warm": {"enabled": True, "wait_seconds": 5},
                "cold": {"enabled": True, "wait_seconds": 30},
                "offsite": {"enabled": True, "never_delete": True},
            }
        },
        "business_data": {
            "stops": {
                "hot": {"enabled": True, "wait_seconds": 10},
                "warm": {"enabled": True, "wait_seconds": 30},
                "cold": {"enabled": True, "wait_seconds": 60},
                "offsite": {"enabled": True, "wait_seconds": 90, "never_delete": False},
            },
            "replicate_to_all": True,
        },
        "job_package": {
            "stops": {
                "hot": {"enabled": True, "wait_seconds": 10},
                "warm": {"enabled": True, "wait_seconds": 20},
                "cold": {"enabled": True, "wait_seconds": 45},
                "offsite": {"enabled": True, "wait_seconds": 60, "never_delete": False},
            }
        },
        "cache": {"cache_seconds": 5},
    }


RULE_SETS_DAYS: dict[str, dict] = _default_stops_days()
RULE_SETS_SECONDS: dict[str, dict] = _default_stops_seconds()


def _get_rule_set(package_type: str | None) -> dict:
    """Return rule set for package type. Default user_data."""
    key = package_type or "user_data"
    sets = RULE_SETS_SECONDS if DEMO_MODE else RULE_SETS_DAYS
    return sets.get(key, sets["user_data"])


def _stops_to_boundaries(rule: dict) -> tuple[int, int, int, str]:
    """Compute (hot_end, warm_end, cold_end, unit) from stops. Cache returns zeros."""
    if "cache_seconds" in rule:
        return 0, 0, 0, "seconds" if DEMO_MODE else "days"
    stops = rule.get("stops", {})
    unit = "seconds" if DEMO_MODE else "days"
    wait_key = "wait_seconds" if DEMO_MODE else "wait_days"
    default = DEFAULT_WAIT_SECONDS if DEMO_MODE else DEFAULT_WAIT_DAYS

    hot_end, warm_end, cold_end = 0, 0, 0
    for i, name in enumerate(BUCKETS_ORDER):
        s = stops.get(name, {})
        enabled = s.get("enabled", True)
        if not enabled:
            continue
        wait = s.get(wait_key)
        if wait is None:
            wait = default
        wait = max(1, int(wait))  # minimum 1 when enabled
        if name == "hot":
            hot_end = wait
        elif name == "warm":
            warm_end = hot_end + wait
        elif name == "cold":
            cold_end = warm_end + wait
        elif name == "offsite":
            pass  # offsite starts after cold_end; never_delete/wait_days used for retention elsewhere
    return hot_end, warm_end, cold_end, unit


def _get_boundaries(package_type: str | None) -> tuple[int, int, int, str]:
    """Return (hot_end, warm_end, cold_end, unit)."""
    r = _get_rule_set(package_type)
    return _stops_to_boundaries(r)


def _validate_stops(stops: dict, demo: bool) -> None:
    """Validate stops: keys, strict order (earlier tier must be enabled before later), enabled+wait min 1."""
    if set(stops.keys()) != set(BUCKETS_ORDER):
        raise ValueError(f"stops must have exactly keys {list(BUCKETS_ORDER)}")
    for name in BUCKETS_ORDER:
        if name not in stops:
            raise ValueError(f"stops missing required key: {name}")
    wait_key = "wait_seconds" if demo else "wait_days"
    prev_enabled = True
    for name in BUCKETS_ORDER:
        s = stops[name]
        if not isinstance(s, dict):
            raise ValueError(f"stops.{name} must be object")
        enabled = s.get("enabled", True)
        if enabled and not prev_enabled:
            raise ValueError(f"stops.{name} enabled requires previous tier to be enabled (strict order)")
        prev_enabled = enabled
        if enabled:
            if name == "offsite" and s.get("never_delete"):
                continue
            wait = s.get(wait_key)
            val = wait if wait is not None else (DEFAULT_WAIT_SECONDS if demo else DEFAULT_WAIT_DAYS)
            if val < 1:
                raise ValueError(f"stops.{name}.{wait_key} must be >= 1 when enabled")


def _bucket_for_age(age: int, package_type: str | None) -> Literal["hot", "warm", "cold", "offsite"]:
    """Derive bucket from age using retention rule set for package type."""
    hot_end, warm_end, cold_end, _ = _get_boundaries(package_type)
    if age < hot_end:
        return "hot"
    if age < warm_end:
        return "warm"
    if age < cold_end:
        return "cold"
    return "offsite"


def _next_job_id() -> str:
    global _JOB_ID
    _JOB_ID += 1
    return f"job-{_JOB_ID}"


def _age_seconds(created_at: str) -> int:
    """Seconds since created_at (UTC)."""
    try:
        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return 0
    delta = datetime.now(timezone.utc) - dt
    return max(0, int(delta.total_seconds()))


def _age_days(created_at: str) -> int:
    """Days since created_at (UTC)."""
    return _age_seconds(created_at) // 86400


def _enrich_job(job: dict) -> dict:
    """Add age_days/age_seconds, bucket, package_id, package_type to job for response."""
    out = dict(job)
    out.setdefault("package_id", job.get("job_id"))
    created = job.get("created_at", "")
    ptype = job.get("package_type") or _tag_to_package_type(job.get("tag")) or "user_data"
    out["package_type"] = ptype
    if DEMO_MODE:
        age = _age_seconds(created)
        out["age_seconds"] = age
        out["age_days"] = age
    else:
        age = _age_days(created)
        out["age_days"] = age
    out["bucket"] = _bucket_for_age(age, ptype)
    if "tier" not in out:
        out["tier"] = out["bucket"]
    return out


# --- Request/response models (JSON, aligned with OpenSpec) ---

def _tag_to_package_type(tag: str | None) -> str:
    """Map legacy tag to package_type."""
    if tag == "backup":
        return "user_data"
    if tag == "audit":
        return "audit_logs"
    if tag == "cache":
        return "cache"
    return "user_data"


class IngestBody(BaseModel):
    source_id: str = Field(..., min_length=1, max_length=256)
    path: str = Field(..., min_length=1, max_length=1024)
    checksum: str | None = None
    size_bytes: int | None = None
    tier_hint: Literal["hot", "warm", "cold"] | None = None
    tag: Literal["backup", "audit", "cache"] | None = None
    package_type: Literal["user_data", "app_logs", "audit_logs", "business_data", "job_package", "cache"] | None = None

    @model_validator(mode="after")
    def checksum_required_when_size_positive(self):
        """OpenSpec §7: checksum required when size_bytes > 0."""
        if self.size_bytes is not None and self.size_bytes > 0 and not self.checksum:
            raise ValueError("checksum is required when size_bytes > 0")
        return self


class JobResponse(BaseModel):
    job_id: str
    source_id: str
    path: str
    status: Literal["pending", "in_progress", "completed", "failed"]
    progress_percent: int = 0
    bucket: Literal["hot", "warm", "cold", "offsite"] = "hot"
    created_at: str
    updated_at: str
    age_days: int = 0


class SourceBody(BaseModel):
    source_id: str = Field(..., min_length=1, max_length=256)
    label: str | None = None


class SourceResponse(BaseModel):
    source_id: str
    label: str | None = None
    last_seen_at: str | None = None


# --- Routes ---

@app.post("/api/v1/ingest", response_model=dict)
def ingest(
    body: IngestBody,
    x_demo_created_secs_ago: int | None = Header(None, alias="X-Demo-Created-Secs-Ago"),
) -> dict:
    """Accept a backup payload; return job_id. Demo: X-Demo-Created-Secs-Ago backdates created_at."""
    job_id = _next_job_id()
    now = datetime.now(timezone.utc)
    if DEMO_MODE and x_demo_created_secs_ago is not None:
        created_dt = now - timedelta(seconds=x_demo_created_secs_ago)
        created_at = created_dt.isoformat()
    else:
        created_at = now.isoformat()
    ptype = body.package_type or _tag_to_package_type(body.tag)
    job = {
        "job_id": job_id,
        "source_id": body.source_id,
        "path": body.path,
        "status": "pending",
        "progress_percent": 0,
        "size_bytes": body.size_bytes or 0,
        "checksum": body.checksum,
        "created_at": created_at,
        "updated_at": now.isoformat(),
        "tag": body.tag,
        "package_type": ptype,
    }
    JOBS[job_id] = job
    # Touch source
    now_str = now.isoformat()
    if body.source_id not in SOURCES:
        SOURCES[body.source_id] = {"source_id": body.source_id, "label": None, "last_seen_at": now_str}
    else:
        SOURCES[body.source_id]["last_seen_at"] = now_str
    return {"job_id": job_id, "package_id": job_id}


@app.get("/api/v1/packages", response_model=list)
@app.get("/api/v1/jobs", response_model=list)
def list_jobs(
    status: str | None = None,
    source_id: str | None = None,
    bucket: Literal["hot", "warm", "cold", "offsite"] | None = None,
) -> list:
    """List packages (alias: jobs); optional filters."""
    out = [_enrich_job(j) for j in JOBS.values()]
    if status:
        out = [j for j in out if j["status"] == status]
    if source_id:
        out = [j for j in out if j["source_id"] == source_id]
    if bucket:
        out = [j for j in out if j["bucket"] == bucket]
    return out


@app.get("/api/v1/packages/{pkg_id}", response_model=dict)
@app.get("/api/v1/jobs/{pkg_id}", response_model=dict)
def get_package(pkg_id: str) -> dict:
    """Get one package by id."""
    if pkg_id not in JOBS:
        raise HTTPException(status_code=404, detail="Package not found")
    return _enrich_job(JOBS[pkg_id])


class PackagePatch(BaseModel):
    progress_percent: int | None = None
    checksum: str | None = None
    status: Literal["pending", "in_progress", "completed", "failed"] | None = None


def _patch_package(pid: str, body: PackagePatch) -> dict:
    """Internal: update package."""
    if pid not in JOBS:
        raise HTTPException(status_code=404, detail="Package not found")
    job = JOBS[pid]
    if body.progress_percent is not None:
        job["progress_percent"] = max(0, min(100, body.progress_percent))
    if body.checksum is not None:
        job["checksum"] = body.checksum
    if body.status is not None:
        job["status"] = body.status
    job["updated_at"] = datetime.now(timezone.utc).isoformat()
    return _enrich_job(job)


@app.patch("/api/v1/packages/{package_id}")
def patch_package(package_id: str, body: PackagePatch = PackagePatch()) -> dict:
    """Update package progress, checksum, or status."""
    return _patch_package(package_id, body)


@app.patch("/api/v1/jobs/{job_id}")
def patch_job(job_id: str, body: PackagePatch = PackagePatch()) -> dict:
    """Update job (alias for package)."""
    return _patch_package(job_id, body)


class ConfigPatch(BaseModel):
    rule_sets: dict | None = None  # { package_type: { stops, replicate_to_all?, cache_seconds? } }


def _rule_sets_for_api() -> dict:
    """Return current rule sets for API (deep copy for mutation safety)."""
    sets = RULE_SETS_SECONDS if DEMO_MODE else RULE_SETS_DAYS
    return copy.deepcopy(sets)


def _deep_merge_rule(target: dict, src: dict, ptype: str, demo: bool) -> None:
    """Merge src into target for package_type. Validates stops if present."""
    if ptype == "cache":
        if "cache_seconds" in src and isinstance(src["cache_seconds"], (int, float)) and src["cache_seconds"] >= 0:
            target["cache_seconds"] = int(src["cache_seconds"])
        return
    if "stops" in src:
        stops = src["stops"]
        if not isinstance(stops, dict):
            raise ValueError("stops must be object")
        _validate_stops(stops, demo)
        target["stops"] = {k: dict(v) for k, v in stops.items()}
    if "replicate_to_all" in src and isinstance(src["replicate_to_all"], bool):
        target["replicate_to_all"] = src["replicate_to_all"]


@app.patch("/api/v1/config")
def patch_config(body: ConfigPatch = ConfigPatch()) -> dict:
    """Update rule sets (stops format). Validates stop order, enabled+wait min 1, offsite never_delete."""
    global RULE_SETS_DAYS, RULE_SETS_SECONDS
    target = RULE_SETS_SECONDS if DEMO_MODE else RULE_SETS_DAYS
    if body.rule_sets:
        for ptype, rule in body.rule_sets.items():
            if ptype not in PACKAGE_TYPES:
                continue
            if not isinstance(rule, dict):
                raise HTTPException(status_code=400, detail=f"rule_sets.{ptype} must be object")
            try:
                base = target.get(ptype, {})
                if ptype == "cache":
                    base = {"cache_seconds": base.get("cache_seconds", 86400 if not DEMO_MODE else 5)}
                else:
                    base = dict(base)
                _deep_merge_rule(base, rule, ptype, DEMO_MODE)
                target[ptype] = base
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
    return get_config()


@app.get("/api/v1/sources", response_model=list)
def list_sources() -> list:
    """List registered sources."""
    return list(SOURCES.values())


@app.post("/api/v1/sources", response_model=dict)
def register_source(body: SourceBody) -> dict:
    """Register a source."""
    now = datetime.now(timezone.utc).isoformat()
    SOURCES[body.source_id] = {
        "source_id": body.source_id,
        "label": body.label,
        "last_seen_at": now,
    }
    return SOURCES[body.source_id]


@app.get("/api/v1/buckets", response_model=dict)
def list_buckets() -> dict:
    """Summary by bucket: counts, sample paths, total size per tier."""
    enriched = [_enrich_job(j) for j in JOBS.values()]
    buckets = []
    for b in BUCKETS_ORDER:
        items = [j for j in enriched if j["bucket"] == b]
        total_bytes = sum(j.get("size_bytes", 0) or 0 for j in items)
        sample = [
            {
                "job_id": j["job_id"],
                "source_id": j["source_id"],
                "path": j["path"],
                "age_days": j["age_days"],
                **({"age_seconds": j["age_seconds"]} if "age_seconds" in j else {}),
            }
            for j in items[:5]
        ]
        buckets.append(
            {
                "name": b,
                "count": len(items),
                "total_bytes": total_bytes,
                "sample": sample,
            }
        )
    return {"buckets": buckets}


@app.get("/api/v1/config", response_model=dict)
def get_config() -> dict:
    """Rule sets per package type. Demo mode returns seconds."""
    rule_sets = _rule_sets_for_api()
    if DEMO_MODE:
        return {"rule_sets": rule_sets, "retention": rule_sets.get("user_data", {}), "demo_mode": True, "unit": "seconds"}
    return {"rule_sets": rule_sets, "retention": rule_sets.get("user_data", {}), "demo_mode": False, "unit": "days"}


@app.get("/api/v1/projections", response_model=dict)
def get_projections(days: int = 5, seconds: int | None = None) -> dict:
    """Objects that will transition in next N days (or N seconds in demo mode)."""
    if DEMO_MODE:
        window = seconds if seconds is not None else days
    else:
        window = days
        seconds = None

    enriched = [_enrich_job(j) for j in JOBS.values()]
    transitions = []
    age_key = "age_seconds" if DEMO_MODE else "age_days"
    unit = "seconds" if DEMO_MODE else "days"

    def will_transition(job: dict, from_b: str, to_b: str, boundary: int) -> bool:
        age = job.get(age_key, job.get("age_days", 0))
        return age < boundary and age + window >= boundary and job["bucket"] == from_b

    segment_defs = [
        ("hot", "warm", "hot_end"),
        ("warm", "cold", "warm_end"),
        ("cold", "offsite", "cold_end"),
    ]
    transition_lists = [[] for _ in segment_defs]
    for j in enriched:
        ptype = j.get("package_type") or "user_data"
        hot_end, warm_end, cold_end, _ = _get_boundaries(ptype)
        boundaries = {"hot_end": hot_end, "warm_end": warm_end, "cold_end": cold_end}
        for idx, (from_b, to_b, end_key) in enumerate(segment_defs):
            if will_transition(j, from_b, to_b, boundaries[end_key]):
                transition_lists[idx].append(j)
                break

    for (from_b, to_b, _), items in zip(segment_defs, transition_lists):
        if items:
            transitions.append({
                "bucket_from": from_b,
                "bucket_to": to_b,
                "count": len(items),
                "jobs": [j["job_id"] for j in items],
            })

    return {
        "days": days,
        "seconds": seconds,
        "window": window,
        "unit": unit,
        "transitions": transitions,
    }


@app.delete("/api/v1/jobs/{job_id}")
def delete_job(job_id: str) -> dict:
    """Delete a job (demo only)."""
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="Job not found")
    job = JOBS.pop(job_id)
    global DELETED_COUNT
    DELETED_COUNT += 1
    return {"deleted": job_id}


@app.delete("/api/v1/jobs")
def delete_jobs_by_tag(tag: Literal["cache"] | None = None) -> dict:
    """Delete jobs by tag or package_type (demo: cache/temp files)."""
    if not tag:
        raise HTTPException(status_code=400, detail="tag required (e.g. ?tag=cache)")
    to_delete = [j for j in JOBS.values() if j.get("tag") == tag or j.get("package_type") == tag]
    for j in to_delete:
        del JOBS[j["job_id"]]
    global DELETED_COUNT
    DELETED_COUNT += len(to_delete)
    return {"deleted": len(to_delete), "job_ids": [j["job_id"] for j in to_delete]}


@app.post("/api/v1/demo/reset")
def demo_reset() -> dict:
    """Reset state for demo (clears jobs, sources, deleted count)."""
    global JOBS, SOURCES, DELETED_COUNT, _JOB_ID
    JOBS.clear()
    SOURCES.clear()
    DELETED_COUNT = 0
    _JOB_ID = 0
    return {"reset": True}


MANIFEST_PATH = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "mock-data" / "MANIFEST.json"

SEED_FILES = (
    [
        {"path": f["path"], "checksum": f.get("checksum", ""), "size_bytes": f.get("size_bytes", 0), "tier_hint": f.get("tier_hint")}
        for f in json.loads(MANIFEST_PATH.read_text()).get("files", [])
    ]
    if MANIFEST_PATH.exists()
    else []
)


@app.post("/api/v1/demo/seed")
def demo_seed(source_id: str = Query("demo-seed")) -> dict:
    """Seed demo data: register source and ingest MANIFEST files."""
    if not SEED_FILES:
        return {"seeded": 0, "message": "MANIFEST.json not found"}
    SOURCES[source_id] = {"source_id": source_id, "label": "Demo seed"}
    count = 0
    for f in SEED_FILES:
        job = _ingest_one(source_id, f["path"], f.get("checksum", ""), f.get("size_bytes", 0), f.get("tier_hint"))
        if job:
            count += 1
    return {"seeded": count, "source_id": source_id}


def _ingest_one(source_id: str, path: str, checksum: str, size_bytes: int, tier_hint: str | None) -> dict | None:
    """Create one job from seed payload. Returns job dict or None."""
    job_id = _next_job_id()
    now = datetime.now(timezone.utc)
    created_at = now.isoformat().replace("+00:00", "Z")
    tag = "backup" if tier_hint == "hot" else ("audit" if tier_hint == "cold" else None)
    ptype = _tag_to_package_type(tag) or "user_data"
    job = {
        "job_id": job_id,
        "source_id": source_id,
        "path": path,
        "status": "pending",
        "progress_percent": 0,
        "size_bytes": size_bytes or 0,
        "checksum": checksum or None,
        "created_at": created_at,
        "updated_at": now.isoformat().replace("+00:00", "Z"),
        "tag": tag,
        "package_type": ptype,
    }
    JOBS[job_id] = job
    if source_id not in SOURCES:
        SOURCES[source_id] = {"source_id": source_id, "label": "Demo seed", "last_seen_at": created_at}
    else:
        SOURCES[source_id]["last_seen_at"] = created_at
    return job


@app.get("/api/v1/status")
def get_status() -> dict:
    """Component status for dashboard: client, catcher, buckets."""
    enriched = [_enrich_job(j) for j in JOBS.values()]
    bucket_counts = {b: sum(1 for j in enriched if j["bucket"] == b) for b in BUCKETS_ORDER}
    # Client "active" if any source seen in last 60s (or 30s in demo)
    now = datetime.now(timezone.utc)
    client_active = False
    for s in SOURCES.values():
        ls = s.get("last_seen_at")
        if ls:
            try:
                dt = datetime.fromisoformat(ls.replace("Z", "+00:00"))
                threshold = 30 if DEMO_MODE else 60
                if (now - dt).total_seconds() < threshold:
                    client_active = True
                    break
            except (ValueError, TypeError):
                pass
    return {
        "demo_mode": DEMO_MODE,
        "components": {
            "client": {"status": "active" if client_active else "idle"},
            "catcher": {"status": "ok", "jobs_count": len(JOBS)},
            "buckets": bucket_counts,
            "deleted_count": DELETED_COUNT,
        },
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
