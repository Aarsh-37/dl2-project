"""Phase 1 demo: parse -> extract -> gaps -> ATS for the 3 sample pairs.

Run from backend/:  python scripts/demo_core.py
Stdlib + local files only (no DB, no network, no LLM).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.ats_service import ats_engine
from app.services.gap_service import compute_gaps
from app.tools import jd_parser, resume_parser, skill_extract
from app.utils.text_clean import section_text
from app.core.config import SAMPLES_DIR, SKILL_TAXONOMY_CSV

PAIRS = [
    ("resume_01_backend_fresher.md", "jd_01_backend_intern.md", 64),
    ("resume_02_frontend.md", "jd_02_frontend.md", 74),
    ("resume_03_data_fresher.md", "jd_03_data_analyst.md", 58),
]


def analyze(resume_name: str, jd_name: str) -> dict:
    taxonomy = skill_extract.load_taxonomy(SKILL_TAXONOMY_CSV)
    resume_text = resume_parser.parse_file(SAMPLES_DIR / resume_name)["text"]
    jd = jd_parser.parse_jd((SAMPLES_DIR / jd_name).read_text(encoding="utf-8"))
    candidate = skill_extract.extract_skills(resume_text, taxonomy)
    required = skill_extract.extract_skills(jd["sections"]["required"], taxonomy)
    preferred = skill_extract.extract_skills(jd["sections"]["preferred"], taxonomy)
    projects_text = section_text(resume_text, "Projects")
    projects = [skill_extract.extract_skills(line, taxonomy) for line in projects_text.split("\n") if line.strip()]
    gaps = compute_gaps(candidate, required, preferred, taxonomy)
    ats = ats_engine(
        {"text": resume_text, "skills": candidate, "projects": projects},
        {"text": jd["text"], "required": required, "preferred": preferred},
    )
    return {"gaps": gaps, "ats": ats}


def main() -> None:
    print(f"{'pair':<8} {'score':<7} {'verdict':<11} {'suggested':<10} {'missing'}")
    for resume_name, jd_name, suggested in PAIRS:
        result = analyze(resume_name, jd_name)
        ats, gaps = result["ats"], result["gaps"]
        missing = ", ".join(m["skill"] for m in gaps["missing"]) or "none"
        print(f"{resume_name[7:9]:<8} {ats['score']:<7} {ats['verdict']:<11} {suggested:<10} {missing}")
        print(f"  breakdown: {ats['breakdown']}")
        print(f"  quick wins: {ats['quick_wins']}")


if __name__ == "__main__":
    main()
