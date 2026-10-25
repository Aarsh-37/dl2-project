"""Gap-function tests, including the eval pair 01 expectation."""
from app.core.config import SAMPLES_DIR, SKILL_TAXONOMY_CSV
from app.services.gap_service import compute_gaps
from app.tools import jd_parser, resume_parser, skill_extract

TAXONOMY = skill_extract.load_taxonomy(SKILL_TAXONOMY_CSV)


def _pair(resume_name: str, jd_name: str) -> tuple[list[str], list[str], list[str]]:
    resume_text = resume_parser.parse_file(SAMPLES_DIR / resume_name)["text"]
    jd = jd_parser.parse_jd((SAMPLES_DIR / jd_name).read_text(encoding="utf-8"))
    candidate = skill_extract.extract_skills(resume_text, TAXONOMY)
    required = skill_extract.extract_skills(jd["sections"]["required"], TAXONOMY)
    preferred = skill_extract.extract_skills(jd["sections"]["preferred"], TAXONOMY)
    return candidate, required, preferred


def test_pair01_missing_is_docker_and_aws():
    candidate, required, preferred = _pair("resume_01_backend_fresher.md", "jd_01_backend_intern.md")
    assert {"Python", "SQL", "Git"} <= set(candidate)
    gaps = compute_gaps(candidate, required, preferred, TAXONOMY)
    assert {"Docker", "AWS"} <= {m["skill"] for m in gaps["missing"]}
    assert gaps["critical_missing"] == []  # Docker/AWS are preferred, not required


def test_no_skill_in_both_strong_and_missing():
    candidate, required, preferred = _pair("resume_02_frontend.md", "jd_02_frontend.md")
    gaps = compute_gaps(candidate, required, preferred, TAXONOMY)
    assert not (set(gaps["strong"]) & {m["skill"] for m in gaps["missing"]})
    assert "React" in gaps["strong"]


def test_missing_carry_criticality_and_weeks():
    gaps = compute_gaps(["Python"], ["Python", "Docker"], ["AWS"], TAXONOMY)
    by_skill = {m["skill"]: m for m in gaps["missing"]}
    assert by_skill["Docker"]["criticality"] == "High"
    assert by_skill["AWS"]["criticality"] == "Medium"
    assert all(m["weeks_to_learn"] >= 1 for m in gaps["missing"])
