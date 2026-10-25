"""In-memory job store (Phase 4.1).

No DB required: POST /analyze runs the deterministic pipeline synchronously
and stores the result here keyed by job_id (= analyses.id when DB lands).
DB persistence is best-effort on top — never a failure mode.
"""
import hashlib
import uuid
from datetime import datetime, timezone

_JOBS: dict[str, dict] = {}
_HASH_INDEX: dict[str, str] = {}  # content hash -> job_id (repeat runs are instant)


def content_hash(resume_text: str, jd_text: str, hours_per_day: int = 3) -> str:
    return hashlib.sha256(
        f"{resume_text}\n---\n{jd_text}\n---\n{hours_per_day}".encode("utf-8")).hexdigest()[:32]


def new_job_id() -> str:
    return str(uuid.uuid4())


def save_job(job_id: str, result: dict, meta: dict) -> None:
    _JOBS[job_id] = {
        "job_id": job_id,
        "status": result.get("status", "partial"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "meta": meta,
        "result": result,
    }
    if meta.get("content_hash"):
        _HASH_INDEX[meta["content_hash"]] = job_id


def find_by_hash(content_hash: str) -> dict | None:
    """Repeat of an identical analysis returns instantly (demo-friendly,
    credit-friendly). The pipeline is deterministic given identical inputs
    except LLM phrasing, which is stable enough to reuse."""
    job_id = _HASH_INDEX.get(content_hash or "")
    if job_id:
        return _JOBS.get(job_id)
    return None


def get_job(job_id: str) -> dict | None:
    return _JOBS.get(job_id)


def delete_job(job_id: str) -> bool:
    job = _JOBS.pop(job_id, None)
    if job is None:
        return False
    chash = (job.get("meta") or {}).get("content_hash")
    if chash and _HASH_INDEX.get(chash) == job_id:
        del _HASH_INDEX[chash]
    return True


def list_jobs(limit: int = 20) -> list[dict]:
    jobs = sorted(_JOBS.values(), key=lambda j: j["created_at"], reverse=True)[:limit]
    return [
        {
            "job_id": j["job_id"],
            "created_at": j["created_at"],
            "role": (j["meta"].get("role") or "Analysis"),
            "score": ((j["result"].get("ats_result") or {}).get("score")),
            "status": j["status"],
        }
        for j in jobs
    ]


# Nodes with real output in v1 (SSE replays these as done).
DONE_NODES_V1 = [
    "resume_analyzer", "jd_analyzer", "ats_engine",
    "skill_gap", "roadmap", "interview",
    "optimizer", "validator", "jobs", "coach",
]
