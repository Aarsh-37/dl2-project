"""POST /analyze (multipart) → 202 {job_id, stream_url}.

Runs the LangGraph graph (LLM agents + checkpointing); falls back to the
deterministic plain-function pipeline when CAREERPILOT_GRAPH=0 or the graph
fails. Validation: file ≤5MB + PDF/DOCX/TXT, JD ≥50 chars → 422 otherwise.
Auth (Phase 4.3): X-User-Id header until Supabase JWT lands.
"""
import os
import tempfile
import threading
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, Header, UploadFile
from fastapi.responses import JSONResponse

from app.api.store import content_hash, find_by_hash, new_job_id, save_job
from app.core.pipeline import run_core_pipeline
from app.tools import resume_parser
from app.utils.text_clean import clean_text

router = APIRouter()

MAX_BYTES = 5 * 1024 * 1024
_ALLOWED_SUFFIX = {".pdf", ".docx", ".doc", ".txt"}
_ALLOWED_MIME = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
}


def _err(message: str, status: int = 422):
    return JSONResponse({"detail": message}, status_code=status)


def _run_pipeline(resume_text: str, jd_text: str, hours_per_day: int,
                  user_id: str | None) -> dict:
    """LangGraph run (checkpointed per thread); deterministic fallback."""
    if os.getenv("CAREERPILOT_GRAPH", "1") == "1":
        try:
            from app.workflows.career_graph import run_graph

            thread = f"{user_id or 'local'}:{uuid.uuid4().hex[:8]}"
            out = run_graph({"user_id": user_id or "local",
                             "hours_per_day": hours_per_day,
                             "resume_text": resume_text,
                             "job_description": jd_text}, thread_id=thread)
            if out.get("ats_result") and out.get("skill_gap"):
                return out
        except Exception:
            pass
    return run_core_pipeline(resume_text=resume_text, jd_text=jd_text,
                             hours_per_day=hours_per_day)


def _persist_best_effort(result: dict, meta: dict, user_id: str | None,
                         job_id: str) -> None:
    """Persist to Supabase when a real user id + reachable DB exist.

    Never raises — the in-memory store is always the primary read path, DB is
    the durable copy used by /history and /result after a restart. Runs in a
    background thread with a caller-supplied job_id so the API response is not
    blocked by the pooler handshake. Until JWT auth lands (Phase 4.3), callers
    pass a Supabase auth.users UUID (X-User-Id or DEMO_USER_ID).
    """
    if not user_id:
        return
    try:
        uid = str(uuid.UUID(user_id))
    except ValueError:
        return
    try:
        from app.db.session import get_session
        from app.services import analysis_service as svc

        db = get_session()
        try:
            svc.save_analysis(
                db, analysis_id=job_id, user_id=uid,
                resume_file_url=f"resumes/{uid}/upload.txt",
                resume_text=result.get("_resume_text", ""),
                jd_text=meta.get("jd_text", ""),
                company=meta.get("company", ""), role=meta.get("role", ""),
                level=meta.get("level", "fresher"),
                hours_per_day=meta.get("hours_per_day", 3),
                candidate_skills=result.get("_candidate", []),
                required=result.get("_required", []),
                preferred=result.get("_preferred", []),
                ats=result.get("ats_result", {}),
                gaps=result.get("skill_gap", {}),
                full_result={**result, "_resume_text": result.get("_resume_text", "")},
            )
        finally:
            db.close()
    except Exception:
        return


@router.post("/analyze", status_code=202)
async def analyze(
    resume_file: UploadFile | None = File(default=None),
    resume_text: str = Form(default=""),
    jd_text: str = Form(default=""),
    company: str = Form(default=""),
    role: str = Form(default=""),
    level: str = Form(default="fresher"),
    hours_per_day: int = Form(default=3),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
):
    if not jd_text or len(clean_text(jd_text)) < 50:
        return _err("jd_text must be at least 50 characters.")
    if level not in {"fresher", "junior", "mid", "senior"}:
        return _err("level must be fresher|junior|mid|senior.")
    hours_per_day = max(1, min(12, int(hours_per_day or 3)))

    text = ""
    if resume_file is not None and resume_file.filename:
        suffix = Path(resume_file.filename).suffix.lower()
        if suffix not in _ALLOWED_SUFFIX:
            return _err("resume_file must be PDF, DOCX, or TXT.")
        if resume_file.content_type and resume_file.content_type not in _ALLOWED_MIME:
            return _err(f"Unexpected MIME: {resume_file.content_type}.")
        raw = await resume_file.read()
        if len(raw) > MAX_BYTES:
            return _err("resume_file must be ≤ 5MB.")
        if not raw.strip():
            return _err("resume_file is empty.")
        if suffix == ".txt":
            text = clean_text(raw.decode("utf-8", errors="ignore"))
        else:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(raw)
                tmp_path = tmp.name
            try:
                text = resume_parser.parse_file(tmp_path)["text"]
            finally:
                Path(tmp_path).unlink(missing_ok=True)
    elif resume_text.strip():
        text = clean_text(resume_text)

    if len(text) < 50:
        return _err("Upload a resume file or paste at least 50 characters of resume text.")

    chash = content_hash(text, jd_text, hours_per_day)
    cached = find_by_hash(chash)
    if cached is not None:
        return {"job_id": cached["job_id"], "stream_url": f"/stream/{cached['job_id']}",
                "cached": True}

    try:
        result = _run_pipeline(text, jd_text, hours_per_day, x_user_id)
    except Exception as exc:  # nodes never raise to the client as 500 without context
        return JSONResponse({"detail": f"Pipeline failed: {exc}"}, status_code=500)

    result["_resume_text"] = text
    meta = {"company": company, "role": role, "level": level,
            "hours_per_day": hours_per_day, "jd_text": jd_text,
            "content_hash": chash}
    job_id = new_job_id()
    save_job(job_id, result, meta)
    # Demo mode: fall back to one real auth user so history survives restarts.
    user_id = x_user_id or os.getenv("DEMO_USER_ID") or None
    if user_id:
        threading.Thread(target=_persist_best_effort,
                         args=(result, meta, user_id, job_id), daemon=True).start()
    return {"job_id": job_id, "stream_url": f"/stream/{job_id}"}
