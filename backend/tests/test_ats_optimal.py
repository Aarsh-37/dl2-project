"""ATS optimality tests: boundary-aware keywords + fuzzy partial gaps."""
from app.services.ats_service import keyword_score
from app.services.gap_service import PARTIAL_RATIO, compute_gaps


def test_keyword_ignores_substring_false_positives():
    text = "Built dashboards with JavaScript and Django. SQL for storage."
    assert keyword_score(text, ["Java"]) == 0.0  # must not match JavaScript
    assert keyword_score(text, ["Go"]) == 0.0  # must not match Django
    assert keyword_score(text, ["JavaScript", "Django", "SQL"]) == 100.0


def test_keyword_matches_real_mentions():
    text = "Java backend with 2 years experience. Go microservices on weekends."
    assert keyword_score(text, ["Java", "Go"]) == 100.0
    assert keyword_score(text, ["Java", "Go", "Rust"]) == round(200 / 3, 1)


def test_fuzzy_partial_for_near_miss_spellings():
    gaps = compute_gaps(["NodeJS"], ["Node.js"], [])
    assert "Node.js" in gaps["partial"]
    assert "Node.js" not in {m["skill"] for m in gaps["missing"]}
    assert gaps["critical_missing"] == []
    detail = {d["skill"]: d for d in gaps["partial_detail"]}
    assert detail["Node.js"]["via"] == "NodeJS"
    assert detail["Node.js"]["similarity"] >= PARTIAL_RATIO


def test_dissimilar_skills_stay_missing():
    gaps = compute_gaps(["Java"], ["JavaScript"], [])
    assert {m["skill"] for m in gaps["missing"]} == {"JavaScript"}
    assert gaps["partial"] == []
    gaps2 = compute_gaps(["React"], ["React Native"], [])
    assert {m["skill"] for m in gaps2["missing"]} == {"React Native"}


def test_partial_never_overlaps_missing_or_strong():
    gaps = compute_gaps(["NodeJS", "Python"], ["Node.js", "Python", "Docker"], [])
    assert set(gaps["strong"]) == {"Python"}
    assert "Node.js" in gaps["partial"]
    assert {m["skill"] for m in gaps["missing"]} == {"Docker"}
    assert not (set(gaps["partial"]) & {m["skill"] for m in gaps["missing"]})
