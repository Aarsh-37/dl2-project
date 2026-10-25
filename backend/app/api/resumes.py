"""Resume approval (HITL) + tailored export (PDF/DOCX, ATS-safe single column)."""
from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from app.api.store import get_job

router = APIRouter()

_APPROVALS: dict[str, dict] = {}


class Approval(BaseModel):
    job_id: str
    approved: bool
    note: str = ""


@router.post("/resumes/approve")
async def approve(body: Approval):
    _APPROVALS[body.job_id] = {"approved": body.approved, "note": body.note}
    return {"ok": True}


class ExportRequest(BaseModel):
    job_id: str
    format: str = "pdf"  # pdf | tex | docx


@router.post("/resumes/export")
async def export_resume(body: ExportRequest):
    """Download the tailored 1-page resume (same Jake-style format, tailored
    to the JD, resume facts only — no upskill section, nothing invented).

    PDF is compiled from the generated LaTeX source (same template as .tex)
    with a hard max-1-page guarantee (tighten + recompile); without a LaTeX
    toolchain it falls back to the reportlab renderer (see X-Pdf-Engine)."""
    job = get_job(body.job_id)
    if job is None:
        return JSONResponse({"detail": "Unknown job_id."}, status_code=404)
    fmt = (body.format or "pdf").lower()
    if fmt not in {"pdf", "tex", "docx"}:
        return JSONResponse({"detail": "format must be pdf|tex|docx."}, status_code=422)
    from app.services import latex_resume as lx
    from app.services import resume_export as rx

    data = rx.build_export_data(job["result"])
    stem = f"resume-{body.job_id[:8]}"
    if fmt == "tex":
        tex = lx.build_latex(data)
        return Response(content=tex.encode("utf-8"), media_type="text/x-tex",
                        headers={"Content-Disposition": f'attachment; filename="{stem}.tex"'})
    if fmt == "docx":
        content = rx.to_docx(data)
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{stem}.docx"'})
    pdf, engine, _tex = lx.build_one_page_pdf(data)
    if pdf is None:
        pdf, engine = rx.to_pdf(data), "reportlab"
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{stem}.pdf"',
                             "X-Pdf-Engine": engine})
