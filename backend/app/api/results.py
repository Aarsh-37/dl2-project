"""Results: GET /result, GET /stream (SSE), GET /history, DELETE /result.

SSE auth (contracts.md §5): short-lived ?token= or Bearer — accepted here but
not enforced until Phase 4.3 (local mode). Client uses fetch + ReadableStream.
"""
import json
import os
import uuid

from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse, StreamingResponse

from app.api.store import DONE_NODES_V1, delete_job, get_job, list_jobs

router = APIRouter()


def _payload(job_id: str, job: dict) -> dict:
    result = job["result"]
    internal = {k for k in result if k.startswith("_")}
    body = {k: v for k, v in result.items() if k not in internal}
    return {"job_id": job_id, "status": job["status"], **body}


def _uid_or_none(user_id: str | None) -> str | None:
    if not user_id:
        return None
    try:
        return str(uuid.UUID(user_id))
    except ValueError:
        return None


def _effective_user(user_id: str | None) -> str | None:
    """Header wins (real auth later); else the demo user owns local runs."""
    return _uid_or_none(user_id) or _uid_or_none(os.getenv("DEMO_USER_ID"))


def _db_load(user_id: str, job_id: str) -> dict | None:
    try:
        from app.db.session import get_session
        from app.services import analysis_service as svc

        db = get_session()
        try:
            return svc.load_analysis(db, user_id=user_id, job_id=job_id)
        finally:
            db.close()
    except Exception:
        return None


def _db_list(user_id: str, limit: int = 20) -> list[dict]:
    try:
        from app.db.session import get_session
        from app.services import analysis_service as svc

        db = get_session()
        try:
            return svc.list_analyses(db, user_id=user_id, limit=limit)
        finally:
            db.close()
    except Exception:
        return []


@router.get("/result/{job_id}")
async def get_result(job_id: str, x_user_id: str | None = Header(default=None, alias="X-User-Id")):
    job = get_job(job_id)
    if job is None:
        uid = _effective_user(x_user_id)
        if uid:
            # Survives API restarts: durable copy in Supabase.
            doc = _db_load(uid, job_id)
            if doc is not None:
                return {"job_id": job_id, **doc}
        return JSONResponse({"detail": "Unknown job_id."}, status_code=404)
    return _payload(job_id, job)


@router.delete("/result/{job_id}")
async def delete_result(job_id: str, x_user_id: str | None = Header(default=None, alias="X-User-Id")):
    found = delete_job(job_id)
    uid = _effective_user(x_user_id)
    if uid:
        try:
            from app.db.session import get_session
            from app.services import analysis_service as svc

            db = get_session()
            try:
                found = svc.delete_analysis(db, user_id=uid, job_id=job_id) or found
            finally:
                db.close()
        except Exception:
            pass
    if not found:
        return JSONResponse({"detail": "Unknown job_id."}, status_code=404)
    # NOTE: Storage-file deletion lands with Supabase wiring (Phase 4.3).
    return {"ok": True}


@router.get("/history")
async def history(x_user_id: str | None = Header(default=None, alias="X-User-Id")):
    items = list_jobs()
    uid = _effective_user(x_user_id)
    if uid:
        seen = {i["job_id"] for i in items}
        for row in _db_list(uid):
            if row["job_id"] not in seen:
                items.append({"job_id": row["job_id"], "created_at": row.get("created_at"),
                              "role": row.get("role") or "Analysis",
                              "score": row.get("ats_score"), "status": row.get("status")})
    items.sort(key=lambda i: i.get("created_at") or "", reverse=True)
    return {"items": items}


@router.get("/stream/{job_id}")
async def stream(job_id: str):
    job = get_job(job_id)

    def frames():
        if job is None:
            yield 'event: error\ndata: {"node":"stream","message":"Unknown job_id."}\n\n'
            return
        for node in DONE_NODES_V1:
            yield f'event: progress\ndata: {json.dumps({"node": node, "status": "done"})}\n\n'
        yield f'event: done\ndata: {json.dumps({"job_id": job_id, "status": job["status"]})}\n\n'

    return StreamingResponse(frames(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache", "X-Accel-Buffering": "no",
    })
