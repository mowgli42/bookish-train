"""
Catcher service: ingest API and job/source tracking.
See openspec/specs/edge-backup-system.md for API and data models.
"""
from datetime import datetime, timezone
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, model_validator

app = FastAPI(title="Edge Backup Catcher", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# In-memory store (replace with DB in later phases)
JOBS: dict[str, dict] = {}
SOURCES: dict[str, dict] = {}
_JOB_ID = 0

# Retention config (Preset A — cloud object storage). Exposed via GET /config.
RETENTION = {
    "hot_days": 7,
    "warm_days": 30,
    "cold_days": 365,
    "offsite_days": 2555,
    "operational_days": 90,
}
# Cumulative boundaries: hot [0,h), warm [h,h+w), cold [h+w,h+w+c), offsite [h+w+c,+inf)
_HOT = RETENTION["hot_days"]
_WARM_END = _HOT + RETENTION["warm_days"]
_COLD_END = _WARM_END + RETENTION["cold_days"]


def _bucket_for_age(age_days: int) -> Literal["hot", "warm", "cold", "offsite"]:
    """Derive bucket from age_days using retention rule set."""
    if age_days < _HOT:
        return "hot"
    if age_days < _WARM_END:
        return "warm"
    if age_days < _COLD_END:
        return "cold"
    return "offsite"


def _next_job_id() -> str:
    global _JOB_ID
    _JOB_ID += 1
    return f"job-{_JOB_ID}"


def _age_days(created_at: str) -> int:
    """Days since created_at (UTC)."""
    try:
        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return 0
    delta = datetime.now(timezone.utc) - dt
    return max(0, delta.days)


def _enrich_job(job: dict) -> dict:
    """Add age_days and bucket to job for response."""
    out = dict(job)
    created = job.get("created_at", "")
    age = _age_days(created)
    out["age_days"] = age
    out["bucket"] = _bucket_for_age(age)
    # Keep tier for backward compat during transition
    if "tier" not in out:
        out["tier"] = out["bucket"]
    return out


# --- Request/response models (JSON, aligned with OpenSpec) ---

class IngestBody(BaseModel):
    source_id: str = Field(..., min_length=1, max_length=256)
    path: str = Field(..., min_length=1, max_length=1024)
    checksum: str | None = None
    size_bytes: int | None = None
    tier_hint: Literal["hot", "warm", "cold"] | None = None

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
def ingest(body: IngestBody) -> dict:
    """Accept a backup payload; return job_id."""
    job_id = _next_job_id()
    now = datetime.now(timezone.utc).isoformat()
    job = {
        "job_id": job_id,
        "source_id": body.source_id,
        "path": body.path,
        "status": "pending",
        "progress_percent": 0,
        "size_bytes": body.size_bytes or 0,
        "created_at": now,
        "updated_at": now,
    }
    JOBS[job_id] = job
    # Touch source
    if body.source_id not in SOURCES:
        SOURCES[body.source_id] = {"source_id": body.source_id, "label": None, "last_seen_at": now}
    else:
        SOURCES[body.source_id]["last_seen_at"] = now
    return {"job_id": job_id}


@app.get("/api/v1/jobs", response_model=list)
def list_jobs(
    status: str | None = None,
    source_id: str | None = None,
    bucket: Literal["hot", "warm", "cold", "offsite"] | None = None,
) -> list:
    """List jobs; optional filters status, source_id, bucket."""
    out = [_enrich_job(j) for j in JOBS.values()]
    if status:
        out = [j for j in out if j["status"] == status]
    if source_id:
        out = [j for j in out if j["source_id"] == source_id]
    if bucket:
        out = [j for j in out if j["bucket"] == bucket]
    return out


@app.get("/api/v1/jobs/{job_id}", response_model=dict)
def get_job(job_id: str) -> dict:
    """Get one job by id."""
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="Job not found")
    return _enrich_job(JOBS[job_id])


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
    """Retention rule set."""
    return {"retention": RETENTION}


@app.get("/api/v1/projections", response_model=dict)
def get_projections(days: int = 5) -> dict:
    """Objects that will transition in next N days."""
    enriched = [_enrich_job(j) for j in JOBS.values()]
    transitions = []

    def will_transition(job: dict, from_b: str, to_b: str, boundary: int) -> bool:
        age = job["age_days"]
        return age < boundary and age + days >= boundary and job["bucket"] == from_b

    # hot → warm at _HOT
    hot_to_warm = [j for j in enriched if will_transition(j, "hot", "warm", _HOT)]
    if hot_to_warm:
        transitions.append(
            {
                "bucket_from": "hot",
                "bucket_to": "warm",
                "count": len(hot_to_warm),
                "jobs": [j["job_id"] for j in hot_to_warm],
            }
        )

    # warm → cold at _WARM_END
    warm_to_cold = [j for j in enriched if will_transition(j, "warm", "cold", _WARM_END)]
    if warm_to_cold:
        transitions.append(
            {
                "bucket_from": "warm",
                "bucket_to": "cold",
                "count": len(warm_to_cold),
                "jobs": [j["job_id"] for j in warm_to_cold],
            }
        )

    # cold → offsite at _COLD_END
    cold_to_offsite = [
        j for j in enriched if will_transition(j, "cold", "offsite", _COLD_END)
    ]
    if cold_to_offsite:
        transitions.append(
            {
                "bucket_from": "cold",
                "bucket_to": "offsite",
                "count": len(cold_to_offsite),
                "jobs": [j["job_id"] for j in cold_to_offsite],
            }
        )

    return {"days": days, "transitions": transitions}


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
