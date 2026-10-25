"""Optimal-resume tests: 1 page max, same format, JD-tailored order,
resume facts only, no upskill section."""
import io

import docx
import fitz

from app.services import latex_resume as lx
from app.services import resume_export as rx

LONG_RESUME = (
    "Jane Doe\njane@example.com | +91-98765 43210\n"
    "Frontend developer with 3 years experience building dashboards.\n"
    "## Education\nB.Sc Computer Science, Pune University, 2021\nM.Sc Data Science, 2023\n"
    "## Experience\n" + "".join(
        f"Frontend Engineer at Company{i}, built feature {i} with React and TypeScript\n"
        f"Shipped dashboard module {i}, Docker containers, AWS deploys\n" for i in range(10)) +
    "## Projects\n" + "".join(
        f"Project {i}: React app with CI/CD pipeline and Kubernetes manifests\n" for i in range(8)) +
    "## Certifications\nAWS Cloud Practitioner 2024\nScrum Master 2023\n"
    "## Achievements\nWon hackathon 2023\nDean's list 2021\n"
)

JD_REQ = ["Docker", "AWS", "Kubernetes"]


def _data():
    out = {
        "optimized_resume": {"summary": "Frontend dev skilled in React."},
        "_candidate": ["React", "JavaScript", "TypeScript", "Docker"],
        "_required": JD_REQ,
        "_resume_text": LONG_RESUME,
        "skill_gap": {"strong": ["React"], "partial": [],
                      "missing": [{"skill": "Go", "criticality": "High",
                                   "reason": "r", "weeks_to_learn": 3}],
                      "critical_missing": ["Go"]},
    }
    return rx.build_export_data(out)


def test_no_upskill_section_anywhere():
    data = _data()
    tex = lx.build_latex(data)
    assert "Upskill" not in tex and "upskill" not in tex.replace("areas_to_upskill", "")
    pdf = rx.to_pdf(data)
    text = "\n".join(p.get_text() for p in fitz.open(stream=pdf, filetype="pdf"))
    assert "Upskill" not in text
    docx = rx.to_docx(data)
    assert b"Upskill" not in docx


def test_one_page_guarantee_long_resume():
    data = _data()
    pdf, engine, _tex = lx.build_one_page_pdf(data)
    assert pdf is not None and engine in {"latex", "latex-tight"}
    assert pdf.startswith(b"%PDF")
    assert len(fitz.open(stream=pdf, filetype="pdf")) == 1


def test_jd_relevant_bullets_first():
    data = _data()
    tex = lx.build_latex(data)
    first_docker = tex.index("Docker")
    assert first_docker < tex.index("Experience") + 3000  # near the top
    # Experience section leads with JD-matching lines.
    exp = tex.split("Experience")[1].split("Skills Summary")[0]
    first_item = exp.split("resumeItemWithoutTitle")[1]
    assert "Docker" in first_item or "AWS" in first_item or "Kubernetes" in first_item


def test_only_resume_facts_rendered():
    data = _data()
    tex = lx.build_latex(data)
    assert "Go" not in tex  # missing skill never appears on the resume
    squashed = tex.replace(" ", "").replace("\\", "")
    # Kept facts (education uncapped, top JD-ranked lines).
    for token in ["PuneUniversity", "Project5", "Docker"]:
        assert token in squashed, token
    # Low-priority overflow honestly capped for 1 page — never invented.
    assert "Company3" not in tex


def test_prioritize_is_stable_and_capped():
    lines = ["plain line one", "Docker deploy pipeline", "plain line two",
             "AWS hosted setup"] + [f"filler {i}" for i in range(20)]
    out = lx.prioritize_lines(lines, ["Docker", "AWS"])
    assert out[0] == "Docker deploy pipeline" and out[1] == "AWS hosted setup"
    assert out[2:] == ["plain line one", "plain line two"] + [f"filler {i}" for i in range(20)]
    tex_lines = lx.build_latex({**_data(), "sections": {
        "education": [], "experience": lines, "projects": [],
        "certifications": [], "activities": []}})
    assert tex_lines.count("\\resumeItemWithoutTitle") <= 7


READABLE = (
    "Jane Doe\njane@example.com | +91-98765 43210\n"
    "## Education\nPune University\nPune, Maharashtra\nB.Tech CSE, 2024\n"
    "## Projects\nPortal - React dashboard\nGitHub\n"
    "\u2022 Built dashboard with React\n- Wrote 20+ SQL queries\n"
    "## Skills\nLanguages: Java, Python\nCloud: AWS, S3\n"
)


def _readable_data():
    return rx.build_export_data(
        {"_resume_text": READABLE, "_candidate": ["Java", "Python", "AWS", "S3"],
         "_required": ["Java"], "optimized_resume": {}, "skill_gap": {}},
        resume_text=READABLE)


def test_skills_render_one_group_per_line():
    data = _readable_data()
    assert [g["label"] for g in data["skill_groups"]] == ["Languages", "Cloud"]
    tex = lx.build_latex(data)
    assert "Languages:" in tex and "Cloud:" in tex
    skills_tex = tex.split("Skills Summary")[1]
    assert "Java, Python, AWS, S3" not in skills_tex  # never one comma soup line
    pdf_text = "\n".join(p.get_text() for p in fitz.open(stream=rx.to_pdf(data), filetype="pdf"))
    assert "Languages: Java, Python" in pdf_text
    document = docx.Document(io.BytesIO(rx.to_docx(data)))
    assert "Languages: Java, Python" in [p.text for p in document.paragraphs]
    assert "Cloud: AWS, S3" in [p.text for p in document.paragraphs]


def test_education_grouped_and_bullets_have_no_double_glyph():
    data = _readable_data()
    edu = data["sections"]["education"][0]
    assert edu["title"] == "Pune University"
    assert any("B.Tech CSE" in d for d in edu["details"])
    project = data["sections"]["projects"][0]
    assert project["title"].startswith("Portal")
    assert project["bullets"] == ["Built dashboard with React", "Wrote 20+ SQL queries"]
    document = docx.Document(io.BytesIO(rx.to_docx(data)))
    texts = [p.text for p in document.paragraphs]
    assert "Built dashboard with React" in texts
    assert not any(t.startswith(("\u2022", "- ")) for t in texts)
