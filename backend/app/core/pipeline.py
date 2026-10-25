"""Phase 4.1 pipeline: plain function (no LangGraph yet).

Deterministic core — files in, dicts out — shaped per contracts.md §5.1.
LLM nodes (explainer, roadmap RAG, interview LLM, optimizer, jobs) land in
Phase 5/6; v1 returns deterministic templates for roadmap/interview and
honest nulls + partial status for the rest.
"""
from functools import lru_cache
import os

from app.core.config import SKILL_TAXONOMY_CSV
from app.services.ats_service import ats_engine, semantic_score
from app.services.gap_service import compute_gaps
from app.tools import jd_parser, skill_extract
from app.utils.text_clean import section_text

# Well-known official docs only — never invent URLs (contracts.md §7).
_DOC_URLS = {
    "Python": "https://docs.python.org/3/tutorial/",
    "JavaScript": "https://developer.mozilla.org/en-US/docs/Web/JavaScript",
    "TypeScript": "https://www.typescriptlang.org/docs/",
    "React": "https://react.dev/learn",
    "Node.js": "https://nodejs.org/en/docs",
    "SQL": "https://www.postgresql.org/docs/",
    "PostgreSQL": "https://www.postgresql.org/docs/",
    "Docker": "https://docs.docker.com/get-started/",
    "Kubernetes": "https://kubernetes.io/docs/home/",
    "AWS": "https://skillbuilder.aws/",
    "Git": "https://git-scm.com/doc",
    "Java": "https://docs.oracle.com/en/java/",
    "Go": "https://go.dev/doc/",
    "Rust": "https://doc.rust-lang.org/book/",
}


@lru_cache(maxsize=1)
def get_taxonomy() -> dict:
    return skill_extract.load_taxonomy(SKILL_TAXONOMY_CSV)


def split_requirements(jd: dict, taxonomy: dict) -> tuple[list[str], list[str]]:
    sections = jd.get("sections", {})
    required = skill_extract.extract_skills(sections.get("required", ""), taxonomy)
    preferred = skill_extract.extract_skills(sections.get("preferred", ""), taxonomy)
    if not required:
        # Plain-text JD with no markdown headings: everything lands in
        # "intro" (dropped from sections), so fall back to the full text.
        required = skill_extract.extract_skills(jd.get("text", ""), taxonomy)
        preferred = []
    return required, preferred


def build_roadmap(gaps: dict, hours_per_day: int) -> dict:
    weeks: list[dict] = []
    for i, item in enumerate(gaps.get("missing", [])[:4], start=1):
        skill = item["skill"]
        url = _DOC_URLS.get(skill)
        resources = [{"title": f"{skill} — official docs", "url": url, "type": "docs"}] if url else []
        weeks.append({
            "week": i,
            "focus": f"{skill} ({item['criticality']} priority)",
            "hours": hours_per_day * 5,
            "tasks": [
                f"Learn {skill} fundamentals (~{item['weeks_to_learn']} wks at {hours_per_day}h/day)",
                f"Build a mini-project evidencing {skill}",
                "Write up what you built + add a resume bullet with a metric",
            ],
            "resources": resources,
            "project": f"Mini-project evidencing {skill}",
            "checkpoint": f"Explain {skill} for 5 minutes + demo the mini-project",
        })
    return {"weeks": weeks}


def build_interview(required: list[str], candidate: list[str]) -> dict:
    technical = []
    for skill in required[:6]:
        known = skill in candidate
        technical.append({
            "q": f"Explain how you have used {skill} in a project (or how you would approach learning it).",
            "difficulty": "Medium" if known else "Easy",
            "why_asked": f"{'Grounded in resume' if known else 'Tests the gap'}: {skill}",
            "ideal_answer": (
                f"Describe a concrete {skill} task: context, approach, trade-off, "
                "and one measurable outcome."
            ),
            "key_points": ["Concrete example", "Trade-off named", "Measurable outcome"],
            "follow_up": f"What would break first if your {skill} solution had 100x load?",
        })
    hr = [
        {
            "q": "Tell me about yourself.",
            "difficulty": "Easy",
            "why_asked": "Standard opener mapped to resume arc",
            "ideal_answer": "Present role (1 line), proof with a metric (2 lines), why this role (1 line).",
            "key_points": ["Present", "Proof", "Fit"],
            "follow_up": "What are you optimizing for in your next role?",
        },
        {
            "q": "Describe a disagreement with a teammate and how you resolved it.",
            "difficulty": "Medium",
            "why_asked": "Behavioral signal for collaboration",
            "ideal_answer": "Situation, options traded off, data or experiment used, agreed rubric going forward.",
            "key_points": ["STAR", "Trade-offs", "Outcome"],
            "follow_up": "What would you do differently?",
        },
    ]
    return {"technical": technical, "hr": hr}


def run_core_pipeline(
    *,
    resume_text: str,
    jd_text: str,
    hours_per_day: int = 3,
) -> dict:
    """Run parse → extract → gaps → ATS → deterministic roadmap/interview.

    Returns a contracts.md §5.1-shaped dict (status done|partial).
    Never raises on empty extraction — returns partial with errors noted.
    """
    taxonomy = get_taxonomy()
    jd = jd_parser.parse_jd(jd_text)
    candidate = skill_extract.extract_skills(resume_text, taxonomy)
    required, preferred = split_requirements(jd, taxonomy)

    projects_text = section_text(resume_text, "Projects")
    projects = [
        skill_extract.extract_skills(line, taxonomy)
        for line in projects_text.split("\n") if line.strip()
    ]

    gaps = compute_gaps(candidate, required, preferred, taxonomy)
    # VAE latent suggestions (experimental enrichment only — never alters
    # strong/partial/missing; [] when the model file is absent).
    try:
        from app.services.skill_vae import enrich_gaps

        gaps = enrich_gaps(gaps, candidate)
    except Exception:
        gaps.setdefault("suggested", [])
    # Semantic embeddings (sentence-transformers) download a ~90MB model on
    # first use — opt-in via CAREERPILOT_SEMANTIC=1 so /analyze stays fast.
    # ats_engine renormalizes weights when semantic is None (v1 behavior).
    sem = None
    if os.getenv("CAREERPILOT_SEMANTIC") == "1":
        try:
            sem = semantic_score(resume_text, jd["text"])
        except Exception:
            sem = None
    ats = ats_engine(
        {"text": resume_text, "skills": candidate, "projects": projects},
        {"text": jd["text"], "required": required, "preferred": preferred},
        semantic=sem,
    )

    missing_names = [m["skill"] for m in gaps.get("missing", [])]
    recommendations = (
        f"Top fixes: {', '.join(missing_names[:3])}. " if missing_names
        else "Strong match — polish metrics and JD keywords. "
    ) + "Roadmap weeks + interview set above are generated from your real gaps (deterministic v1)."

    errors: list[dict] = []
    if not required:
        errors.append({"node": "jd_analyzer", "message": "No skills detected in JD — check JD text."})

    return {
        "ats_result": ats,
        "skill_gap": gaps,
        "roadmap": build_roadmap(gaps, hours_per_day),
        "interview_questions": build_interview(required, candidate),
        "optimized_resume": None,
        "validation_result": None,
        "jobs": [],
        "job_matches": [],
        "career_recommendations": recommendations,
        "errors": errors,
        "agent_trace": [],  # deterministic path makes no LLM calls
        "status": "partial",  # optimizer/validator/jobs are later phases
        "_required": required,
        "_preferred": preferred,
        "_candidate": candidate,
    }
