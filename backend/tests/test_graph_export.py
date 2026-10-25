"""Graph + export tests: deterministic (CAREERPILOT_LLM=0 via conftest)."""
from fastapi.testclient import TestClient

from app.main import app
from app.services import resume_export as rx
from app.workflows.career_graph import run_sync

RESUME = (
    "Jane Doe\njane@example.com\nFrontend dev with 1 year experience. "
    "Skills: React, JavaScript, TypeScript, CSS. "
    "Projects: dashboard app built with React. Education: B.Sc."
)
JD = (
    "Hiring Frontend Developer for our product team. Required: React, "
    "TypeScript, CSS, Docker. Preferred: JavaScript, AWS. Must have 1 year "
    "experience building dashboards and shipping features."
)


def test_run_sync_shape_and_status():
    out = run_sync({"resume_text": RESUME, "job_description": JD})
    for key in ("ats_result", "skill_gap", "roadmap", "interview_questions",
                "career_recommendations", "status"):
        assert key in out, key
    assert out["status"] in {"done", "partial"}
    assert set(out["skill_gap"]["strong"]) >= {"React", "TypeScript", "CSS"}
    assert out["_required"] and out["_candidate"]
    assert 0 <= out["ats_result"]["score"] <= 100


def test_export_bytes_honest():
    out = run_sync({"resume_text": RESUME, "job_description": JD})
    out["_resume_text"] = RESUME
    data = rx.build_export_data(out)
    assert data["contact"]["email"] == "jane@example.com"
    assert data["name"] == "Jane Doe"
    for gap in data["upskill"]:
        assert gap not in data["summary"] or "upskill" in data["summary"].lower()
    pdf, docx = rx.to_pdf(data), rx.to_docx(data)
    assert pdf.startswith(b"%PDF") and len(pdf) > 1000
    assert docx.startswith(b"PK") and len(docx) > 1000


def test_export_endpoint_pdf_docx():
    c = TestClient(app)
    r = c.post("/analyze", data={"resume_text": RESUME, "jd_text": JD})
    assert r.status_code == 202, r.text
    job = r.json()["job_id"]
    for fmt, magic, ctype in (("pdf", b"%PDF", "application/pdf"),
                              ("docx", b"PK", "application/vnd.openxmlformats")):
        e = c.post("/resumes/export", json={"job_id": job, "format": fmt})
        assert e.status_code == 200, e.text
        assert e.content.startswith(magic)
        assert ctype in e.headers["content-type"]
    assert c.post("/resumes/export", json={"job_id": "nope", "format": "pdf"}).status_code == 404
    assert c.post("/resumes/export", json={"job_id": job, "format": "txt"}).status_code == 422
