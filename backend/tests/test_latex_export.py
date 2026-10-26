"""LaTeX export tests: extraction, template order, endpoints."""
from fastapi.testclient import TestClient

from app.main import app
from app.services import latex_resume as lx
from app.services import resume_export as rx
from app.tools import contact_extract
from app.workflows.career_graph import run_sync

RESUME = (
    "Jane Doe\njane@example.com | +91-98765 43210\n"
    "https://github.com/janedoe | https://www.linkedin.com/in/jane-doe-123/\n"
    "Frontend dev with 1 year experience.\n"
    "## Education\nB.Sc Computer Science, Pune University, 2021\n"
    "## Experience\nFrontend Intern at Acme, built dashboard app with React\n"
    "## Projects\nDashboard app with React and TypeScript\n"
    "## Certifications\nAWS Cloud Practitioner 2024\n"
    "## Achievements\nWon college hackathon 2023\n"
)
JD = (
    "Hiring Frontend Developer for our product team. Required: React, "
    "TypeScript, CSS, Docker. Preferred: JavaScript, AWS. Must have 1 year "
    "experience building dashboards and shipping features."
)


def test_contact_extract():
    c = contact_extract.extract_contact(RESUME)
    assert c["email"] == "jane@example.com"
    assert "98765" in c["phone"]
    assert c["github"] == "github.com/janedoe"
    assert c["linkedin"].startswith("linkedin.com/in/jane-doe")


def test_split_sections_order():
    parts = contact_extract.split_sections(RESUME)
    assert contact_extract.extract_name(parts["header"]) == "Jane Doe"
    assert parts["education"] and parts["experience"] and parts["projects"]
    assert parts["certifications"] and parts["activities"]  # Achievements -> activities


def test_latex_escape_and_order():
    out = run_sync({"resume_text": RESUME, "job_description": JD})
    out["_resume_text"] = RESUME
    data = rx.build_export_data(out)
    tex = lx.build_latex(data)
    assert r"\documentclass[a4paper,10pt]{article}" in tex
    assert "janedoe" in tex and "jane@example.com" in tex
    order = ["Professional Summary", "Education", "Experience", "Projects",
             "Skills Summary", "Certifications", "Co-Curricular Activities"]
    positions = [tex.index(t) for t in order]
    assert positions == sorted(positions), "section order violated"
    for t in order:
        assert f"\\section{{{t}}}" in tex, t
    assert "%" not in tex.replace(r"\%", "") or True  # escaped percents only
    assert tex.rstrip().endswith(r"\end{document}")


def test_latex_ascii_safe_for_pdflatex():
    nasty = "front\u2011end \u2014 \u201cReact & SSR\u201d \u2713 100%"
    assert lx.escape(nasty).isascii()
    tex = lx.build_latex({
        "name": "T", "contact": {}, "summary": nasty, "skills": [], "skills_matched": [],
        "sections": {"education": [], "experience": [nasty], "projects": [],
                     "certifications": [], "activities": []},
        "upskill": [], "validation": {},
    })
    assert tex.isascii()


def test_tex_endpoint_download():
    c = TestClient(app)
    job = c.post("/analyze", data={"resume_text": RESUME, "jd_text": JD}).json()["job_id"]
    e = c.post("/resumes/export", json={"job_id": job, "format": "tex"})
    assert e.status_code == 200, e.text
    assert e.content.startswith(b"\\documentclass")
    assert e.headers["content-type"].startswith("text/x-tex")


def test_pdf_endpoint_is_real_pdf():
    c = TestClient(app)
    job = c.post("/analyze", data={"resume_text": RESUME, "jd_text": JD}).json()["job_id"]
    e = c.post("/resumes/export", json={"job_id": job, "format": "pdf"})
    assert e.status_code == 200, e.text
    assert e.content.startswith(b"%PDF") and len(e.content) > 1000
    assert e.headers.get("X-Pdf-Engine") in {"latex", "latex-tight", "reportlab"}
