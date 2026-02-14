"""
Catcher service: ingest API and job/source tracking.
See openspec/specs/edge-backup-system.md for API and data models.
Demo mode: DEMO_MODE=1 uses retention in seconds for 2-min walkthrough.
"""
import os
from datetime import datetime, timezone, timedelta
from typing import Literal

from fastapi import FastAPI, HTTPException, Header
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

# Rule sets by package type. Each has hot/warm/cold/offsite (days or seconds), optional replicate_to_all, cache_seconds for cache.
RULE_SETS_DAYS: dict[str, dict] = {
    "user_data": {"hot_days": 7, "warm_days": 30, "cold_days": 365, "offsite_days": 2555},
    "app_logs": {"hot_days": 3, "warm_days": 14, "cold_days": 90, "offsite_days": 365},
    "audit_logs": {"hot_days": 0, "warm_days": 7, "cold_days": 365, "offsite_days": 2555},
    "business_data": {"hot_days": 7, "warm_days": 30, "cold_days": 365, "offsite_days": 2555, "replicate_to_all": True},
    "job_package": {"hot_days": 7, "warm_days": 30, "cold_days": 90, "offsite_days": 365},
    "cache": {"cache_seconds": 86400, "hot_days": 0, "warm_days": 0, "cold_days": 0, "offsite_days": 0},
}

RULE_SETS_SECONDS: dict[str, dict] = {
    "user_data": {"hot_seconds": 10, "warm_seconds": 30, "cold_seconds": 60, "offsite_seconds": 90},
    "app_logs": {"hot_seconds": 5, "warm_seconds": 15, "cold_seconds": 45, "offsite_seconds": 60},
    "audit_logs": {"hot_seconds": 0, "warm_seconds": 5, "cold_seconds": 30, "offsite_seconds": 90},
    "business_data": {"hot_seconds": 10, "warm_seconds": 30, "cold_seconds": 60, "offsite_seconds": 90, "replicate_to_all": True},
    "job_package": {"hot_seconds": 10, "warm_seconds": 20, "cold_seconds": 45, "offsite_seconds": 60},
    "cache": {"cache_seconds": 5, "hot_seconds": 0, "warm_seconds": 0, "cold_seconds": 0, "offsite_seconds": 0},
}


def _get_rule_set(package_type: str | None) -> dict:
    """Return rule set for package type. Default user_data."""
    key = package_type or "user_data"
    sets = RULE_SETS_SECONDS if DEMO_MODE else RULE_SETS_DAYS
    return sets.get(key, sets["user_data"])


def _get_boundaries(package_type: str | None) -> tuple[int, int, int, str]:
    """Return (hot_end, warm_end, cold_end, unit)."""
    r = _get_rule_set(package_type)
    if DEMO_MODE:
        h = r.get("hot_seconds", 0)
        w = h + r.get("warm_seconds", 0)
        c = w + r.get("cold_seconds", 0)
        return h, w, c, "seconds"
    h = r.get("hot_days", 0)
    w = h + r.get("warm_days", 0)
    c = w + r.get("cold_days", 0)
    return h, w, c, "days"


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
    for j in out:
        j.setdefault("package_id", j["job_id"])
    return out


@app.get("/api/v1/packages/{pkg_id}", response_model=dict)
@app.get("/api/v1/jobs/{pkg_id}", response_model=dict)
def get_package(pkg_id: str) -> dict:
    """Get one package by id."""
    if pkg_id not in JOBS:
        raise HTTPException(status_code=404, detail="Package not found")
    out = _enrich_job(JOBS[pkg_id])
    out.setdefault("package_id", out["job_id"])
    return out


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
    retention: dict | None = None
    rule_sets: dict | None = None  # { package_type: { hot_days, warm_days, ... } }


def _rule_sets_for_api() -> dict:
    """Return current rule sets for API (dict of package_type -> rule)."""
    sets = RULE_SETS_SECONDS if DEMO_MODE else RULE_SETS_DAYS
    return {k: dict(v) for k, v in sets.items()}


@app.patch("/api/v1/config")
def patch_config(body: ConfigPatch = ConfigPatch()) -> dict:
    """Update retention or rule sets (MVP: in-memory)."""
    global RULE_SETS_DAYS, RULE_SETS_SECONDS
    target = RULE_SETS_SECONDS if DEMO_MODE else RULE_SETS_DAYS
    if body.rule_sets:
        for ptype, rule in body.rule_sets.items():
            if ptype in PACKAGE_TYPES and isinstance(rule, dict):
                for k, v in rule.items():
                    if isinstance(v, (int, float)) and v >= 0:
                        target.setdefault(ptype, {}).update({k: int(v)})
                    elif k == "replicate_to_all" and isinstance(v, bool):
                        target.setdefault(ptype, {})["replicate_to_all"] = v
    if body.retention:
        for k, v in body.retention.items():
            if isinstance(v, (int, float)) and v >= 0:
                for ptype in target:
                    if k in target.get(ptype, {}):
                        target[ptype][k] = int(v)
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
    buckets_order = ["hot", "warm", "cold", "offsite"]
    buckets = []
    for b in buckets_order:
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

    hot_to_warm = []
    warm_to_cold = []
    cold_to_offsite = []
    for j in enriched:
        ptype = j.get("package_type") or "user_data"
        hot_end, warm_end, cold_end, _ = _get_boundaries(ptype)
        if will_transition(j, "hot", "warm", hot_end):
            hot_to_warm.append(j)
        if will_transition(j, "warm", "cold", warm_end):
            warm_to_cold.append(j)
        if will_transition(j, "cold", "offsite", cold_end):
            cold_to_offsite.append(j)

    if hot_to_warm:
        transitions.append(
            {"bucket_from": "hot", "bucket_to": "warm", "count": len(hot_to_warm), "jobs": [j["job_id"] for j in hot_to_warm]}
        )
    if warm_to_cold:
        transitions.append(
            {"bucket_from": "warm", "bucket_to": "cold", "count": len(warm_to_cold), "jobs": [j["job_id"] for j in warm_to_cold]}
        )
    if cold_to_offsite:
        transitions.append(
            {
                "bucket_from": "cold",
                "bucket_to": "offsite",
                "count": len(cold_to_offsite),
                "jobs": [j["job_id"] for j in cold_to_offsite],
            }
        )

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


@app.get("/api/v1/status")
def get_status() -> dict:
    """Component status for dashboard: client, catcher, buckets."""
    enriched = [_enrich_job(j) for j in JOBS.values()]
    bucket_counts = {}
    for b in ["hot", "warm", "cold", "offsite"]:
        bucket_counts[b] = sum(1 for j in enriched if j["bucket"] == b)
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
