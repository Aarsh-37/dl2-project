"""ATS engine tests: weights, bounds, monotonicity, verdicts."""
from app.core.config import ATS_WEIGHTS_V1, SAMPLES_DIR, SKILL_TAXONOMY_CSV
from app.services.ats_service import ats_engine, skill_score
from app.services.gap_service import compute_gaps
from app.tools import jd_parser, resume_parser, skill_extract
from app.utils.text_clean import section_text

TAXONOMY = skill_extract.load_taxonomy(SKILL_TAXONOMY_CSV)


def _profiles(resume_name: str, jd_name: str) -> tuple[dict, dict]:
    resume_text = resume_parser.parse_file(SAMPLES_DIR / resume_name)["text"]
    jd = jd_parser.parse_jd((SAMPLES_DIR / jd_name).read_text(encoding="utf-8"))
    candidate = skill_extract.extract_skills(resume_text, TAXONOMY)
    required = skill_extract.extract_skills(jd["sections"]["required"], TAXONOMY)
    preferred = skill_extract.extract_skills(jd["sections"]["preferred"], TAXONOMY)
    projects_text = section_text(resume_text, "Projects")
    projects = [skill_extract.extract_skills(line, TAXONOMY) for line in projects_text.split("\n") if line.strip()]
    return (
        {"text": resume_text, "skills": candidate, "projects": projects},
        {"text": jd["text"], "required": required, "preferred": preferred},
    )


def test_weights_sum_to_one():
    assert abs(sum(ATS_WEIGHTS_V1.values()) - 1.0) < 1e-9


def test_scores_bounded_and_verdict_consistent():
    resume, jd = _profiles("resume_01_backend_fresher.md", "jd_01_backend_intern.md")
    result = ats_engine(resume, jd)
    assert 0 <= result["score"] <= 100
    assert result["verdict"] in {"Strong", "Moderate", "Needs Work"}
    assert set(result["breakdown"]) == set(ATS_WEIGHTS_V1) - {"semantic"} | {"semantic"}
    assert result["breakdown"]["semantic"] is None  # no embeddings in Phase 1


def test_adding_a_missing_skill_never_lowers_score():
    resume, jd = _profiles("resume_01_backend_fresher.md", "jd_01_backend_intern.md")
    before = ats_engine(resume, jd)["score"]
    resume["skills"] = sorted(set(resume["skills"]) | {"Docker"})
    after = ats_engine(resume, jd)["score"]
    assert after >= before


def test_sample_pairs_within_ten_of_suggested_labels():
    # Suggested human labels (eval_set.csv pairs 01-03): 64 / 74 / 58.
    cases = [
        ("resume_01_backend_fresher.md", "jd_01_backend_intern.md", 64),
        ("resume_02_frontend.md", "jd_02_frontend.md", 74),
        ("resume_03_data_fresher.md", "jd_03_data_analyst.md", 58),
    ]
    for resume_name, jd_name, suggested in cases:
        resume, jd = _profiles(resume_name, jd_name)
        score = ats_engine(resume, jd)["score"]
        assert abs(score - suggested) <= 10, (resume_name, score, suggested)


def test_skill_score_weights_required_double():
    assert skill_score(["A"], [], ["A"]) == 100.0
    assert skill_score(["A", "B"], ["C"], ["A"]) < skill_score(["A", "B"], ["C"], ["A", "C"])
    gaps = compute_gaps(["A"], ["A", "B"], ["C"], TAXONOMY)
    assert gaps["strong"] == ["A"]
