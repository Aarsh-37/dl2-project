"""Deterministic ATS engine. Python calculates; the LLM only explains (Phase 2).

Weights frozen in contracts.md §3 (mirrored in app.core.config).
Without a semantic score (Phase 2 embeddings) the remaining weights are
renormalized so v1 still sums to 1.0 — the response flags semantic as "n/a".

Input shapes (dicts, no DB):
  resume: {"text": str, "skills": [canonical...], "projects": [[stack...], ...]}
  jd:     {"text": str, "required": [...], "preferred": [...]}
Output: {"score", "breakdown", "verdict", "strengths", "gaps",
         "improvements", "quick_wins", "rationale"} (contracts.md §4).
"""
import re

from app.core.config import ATS_VERDICTS, ATS_WEIGHTS_V1

_YEARS = re.compile(r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)", re.I)
# Degree abbreviations require the dot (or no space): "B com" inside normal
# prose (e.g. "A/B comparisons") must never count as B.Com.
_DEGREE_PATTERNS = (
    (r"\bb\.tech\b|\bbtech\b", "b.tech"), (r"\bm\.tech\b|\bmtech\b", "m.tech"),
    (r"\bb\.sc\b|\bbsc\b", "b.sc"), (r"\bm\.sc\b|\bmsc\b", "m.sc"),
    (r"\bb\.com\b|\bbcom\b", "b.com"), (r"\bmba\b", "mba"),
    (r"bachelor", "bachelor"), (r"master", "master"),
    (r"\bphd\b|\bph\.?d\b", "phd"), (r"diploma", "diploma"),
    (r"degree", "degree"),
)


def _recall(have: set, need: list) -> float:
    if not need:
        return 100.0
    return round(100.0 * len(have & set(need)) / len(need), 1)


def keyword_score(resume_text: str, keywords: list[str]) -> float:
    # Keyword match = recall over JD skill terms evidenced in the resume text.
    # Boundary-aware (skill_extract.contains_term): "Go" must not match
    # "Django", "Java" must not match "JavaScript". (Caller passes
    # required + preferred canonical names.)
    from app.tools.skill_extract import contains_term

    if not keywords:
        return 100.0
    hits = sum(1 for kw in keywords if contains_term(resume_text or "", kw))
    return round(100.0 * hits / len(keywords), 1)


def skill_score(required: list[str], preferred: list[str], candidate: list[str]) -> float:
    required = required or []
    preferred = preferred or []
    denom = 2 * len(required) + len(preferred)
    if denom == 0:
        return 100.0
    have = set(candidate or [])
    numer = 2 * len(have & set(required)) + len(have & set(preferred))
    return round(100.0 * numer / denom, 1)


def _years_mentioned(text: str) -> float:
    found = [float(m.group(1)) for m in _YEARS.finditer(text or "")]
    return min(max(found) if found else 0.0, 10.0)


def experience_score(resume_text: str, jd_text: str) -> float:
    required = _years_mentioned(jd_text)
    if required <= 1.0:
        lowered = (resume_text or "").lower()
        return 75.0 if ("intern" in lowered or "project" in lowered) else 50.0
    have = _years_mentioned(resume_text)
    return round(100.0 * min(have / required, 1.0), 1)


def _degrees(text: str) -> set[str]:
    lowered = (text or "").lower()
    return {label for pattern, label in _DEGREE_PATTERNS if re.search(pattern, lowered)}


def education_score(resume_text: str, jd_text: str) -> float:
    jd_degrees = _degrees(jd_text)
    if not jd_degrees:
        return 80.0
    resume_degrees = _degrees(resume_text)
    if resume_degrees & jd_degrees:
        return 100.0
    return 60.0 if resume_degrees else 30.0


def project_relevance(projects: list[list[str]], required: list[str]) -> float:
    if not projects:
        return 50.0
    union: set[str] = set()
    for stack in projects:
        union.update(stack or [])
    return _recall(union, required or [])


def semantic_score(resume_text: str, jd_text: str) -> float | None:
    """Cosine similarity via the shared, boot-warmed ST model (tools.embeddings).

    Reuses that singleton + its SHA256 cache instead of loading a second
    all-MiniLM-L6-v2 — keeps the first semantic request warm and repeat runs
    instant. Returns None when sentence-transformers is absent.
    """
    try:
        from app.tools.embeddings import semantic_score as _score
    except ImportError:
        return None
    return _score(resume_text, jd_text)


def _verdict(score: float) -> str:
    if score >= ATS_VERDICTS["strong"]:
        return "Strong"
    if score >= ATS_VERDICTS["moderate"]:
        return "Moderate"
    return "Needs Work"


def ats_engine(resume: dict, jd: dict, semantic: float | None = None) -> dict:
    required = jd.get("required", [])
    preferred = jd.get("preferred", [])
    candidate = resume.get("skills", [])

    components = {
        "keyword": keyword_score(resume.get("text", ""), required + preferred),
        "skill": skill_score(required, preferred, candidate),
        "semantic": semantic,
        "experience": experience_score(resume.get("text", ""), jd.get("text", "")),
        "education": education_score(resume.get("text", ""), jd.get("text", "")),
        "project_relevance": project_relevance(resume.get("projects", []), required),
    }
    weights = dict(ATS_WEIGHTS_V1)
    if components["semantic"] is None:
        weights.pop("semantic")
    total = sum(weights.values())
    score = round(sum(components[k] * w / total for k, w in weights.items()), 1)
    breakdown = {k: (None if v is None else round(v, 1)) for k, v in components.items()}

    from app.services.gap_service import compute_gaps
    gaps = compute_gaps(candidate, required, preferred)
    strengths = gaps["strong"][:5]
    missing_names = [m["skill"] for m in gaps["missing"][:5]]
    quick_wins = []
    if missing_names:
        quick_wins.append(f"Add '{missing_names[0]}' to skills with one project bullet evidencing it.")
    quick_wins.append("Quantify 2 experience bullets with metrics (users, %, response time).")
    if strengths:
        quick_wins.append(f"Move the project evidencing '{strengths[0]}' higher in the resume.")
    return {
        "score": score,
        "breakdown": breakdown,
        "verdict": _verdict(score),
        "strengths": strengths,
        "gaps": missing_names,
        "improvements": [f"Bridge '{m}' via a mini-project (see roadmap)." for m in missing_names[:3]],
        "quick_wins": quick_wins[:3],
        "rationale": (
            f"Matched {len(gaps['strong'])}/{len(required)} required skills; "
            f"missing: {', '.join(missing_names) if missing_names else 'none'}."
        ),
    }
