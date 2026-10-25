"""Pipeline tests: plain-text JD fallback + perfect-match edge (no DB, no LLM)."""
from app.core.pipeline import run_core_pipeline

RESUME = (
    "Jane, Frontend dev with 1 year experience. Skills: React, JavaScript, "
    "TypeScript, CSS. Projects: dashboard app built with React. Education: B.Sc."
)
JD_PLAIN = (
    "Hiring Frontend Developer. Required: React, TypeScript, CSS. "
    "Preferred: JavaScript. Must have 1 year experience building dashboards."
)


def test_plain_text_jd_extracts_required():
    result = run_core_pipeline(resume_text=RESUME, jd_text=JD_PLAIN)
    assert result["errors"] == []
    assert set(result["skill_gap"]["strong"]) >= {"React", "TypeScript", "CSS"}


def test_perfect_match_empty_roadmap_still_partial():
    result = run_core_pipeline(resume_text=RESUME, jd_text=JD_PLAIN)
    assert result["skill_gap"]["missing"] == []
    assert result["roadmap"] == {"weeks": []}
    assert result["status"] == "partial"  # optimizer/jobs are later phases


def test_short_inputs_still_return_shapes():
    result = run_core_pipeline(
        resume_text="John has Python and SQL skills with 2 years experience. B.Tech degree.",
        jd_text="Need Python and SQL developers with 2 years experience and B.Tech degree "
        "for backend microservices work in our growing team.",
    )
    assert "ats_result" in result and "skill_gap" in result
    assert 0 <= result["ats_result"]["score"] <= 100
