"""Parser + taxonomy tests. Stdlib + local files only."""
from pathlib import Path

from app.core.config import SAMPLES_DIR, SKILL_TAXONOMY_CSV
from app.tools import jd_parser, resume_parser, skill_extract


def test_taxonomy_loads_about_300_skills():
    taxonomy = skill_extract.load_taxonomy(SKILL_TAXONOMY_CSV)
    assert len(taxonomy["terms"]) >= 290


def test_aliases_resolve_to_canonical():
    taxonomy = skill_extract.load_taxonomy(SKILL_TAXONOMY_CSV)
    assert skill_extract.normalize_skill("JS", taxonomy) == "JavaScript"
    assert skill_extract.normalize_skill("K8s", taxonomy) == "Kubernetes"
    assert skill_extract.normalize_skill("Postgres", taxonomy) == "PostgreSQL"


def test_code_boundaries_avoid_false_positives():
    taxonomy = skill_extract.load_taxonomy(SKILL_TAXONOMY_CSV)
    assert "C" not in skill_extract.extract_skills("Worked with C++ on embedded targets.", taxonomy)
    assert "C++" in skill_extract.extract_skills("Worked with C++ on embedded targets.", taxonomy)
    assert "SQL" not in skill_extract.extract_skills("Used SQLite for local storage.", taxonomy)


def test_sample_resumes_parse_to_text():
    for name in ("resume_01_backend_fresher.md", "resume_02_frontend.md", "resume_03_data_fresher.md"):
        parsed = resume_parser.parse_file(SAMPLES_DIR / name)
        assert len(parsed["text"]) > 200, name


def test_jd_sections_split_required_preferred():
    jd = jd_parser.parse_jd((SAMPLES_DIR / "jd_01_backend_intern.md").read_text(encoding="utf-8"))
    assert "Python" in jd["sections"]["required"]
    assert "Docker" in jd["sections"]["preferred"]
