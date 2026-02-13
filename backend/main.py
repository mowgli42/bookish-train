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


def _next_job_id() -> str:
    global _JOB_ID
    _JOB_ID += 1
    return f"job-{_JOB_ID}"


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
    tier: str = "hot"
    created_at: str
    updated_at: str


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
        "tier": body.tier_hint or "hot",
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
def list_jobs(status: str | None = None, source_id: str | None = None) -> list:
    """List jobs; optional filters status, source_id."""
    out = list(JOBS.values())
    if status:
        out = [j for j in out if j["status"] == status]
    if source_id:
        out = [j for j in out if j["source_id"] == source_id]
    return out


@app.get("/api/v1/jobs/{job_id}", response_model=dict)
def get_job(job_id: str) -> dict:
    """Get one job by id."""
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="Job not found")
    return JOBS[job_id]


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


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
