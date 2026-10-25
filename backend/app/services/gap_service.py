"""Deterministic skill-gap computation. No LLM, no DB.

Contract shape (frozen in contracts.md §4):
  {"strong", "partial", "missing": [{skill, criticality, reason, weeks_to_learn}],
   "critical_missing"}
Rules: required-missing -> High; preferred-missing -> Medium; near-miss
spellings (NodeJS ~ Node.js) surface as partial with evidence instead of
a harsh High gap. Extra transparency key: partial_detail [{skill, via}].
Invariant: nothing appears in both strong and missing.
"""
import difflib

from app.core.config import DEFAULT_WEEKS_TO_LEARN, WEEKS_TO_LEARN_BY_CATEGORY

# Near-miss threshold: "NodeJS"~"Node.js" (0.92) and "ReactJS"~"React" (0.83)
# count as related; "Java"~"JavaScript" (0.57) and "React"~"React Native"
# (0.59) correctly do not.
PARTIAL_RATIO = 0.8


def weeks_for(skill: str, taxonomy: dict | None = None) -> int:
    if taxonomy:
        category = taxonomy["category"].get(skill)
        if category and category in WEEKS_TO_LEARN_BY_CATEGORY:
            return WEEKS_TO_LEARN_BY_CATEGORY[category]
    return DEFAULT_WEEKS_TO_LEARN


def _best_fuzzy(skill: str, candidate: set[str]) -> tuple[str | None, float]:
    """Closest candidate skill by name similarity, or (None, 0.0)."""
    best, score = None, 0.0
    for cand in candidate:
        if len(skill) < 2 or len(cand) < 2:
            continue
        ratio = difflib.SequenceMatcher(None, skill.lower(), cand.lower()).ratio()
        if ratio > score:
            best, score = cand, ratio
    return (best, score) if score >= PARTIAL_RATIO else (None, 0.0)


def compute_gaps(
    candidate_skills: list[str],
    required: list[str],
    preferred: list[str],
    taxonomy: dict | None = None,
) -> dict:
    candidate = set(candidate_skills or [])
    required_unique = list(dict.fromkeys(required or []))
    preferred_unique = [s for s in dict.fromkeys(preferred or []) if s not in required_unique]

    strong = [s for s in required_unique if s in candidate]
    partial = [s for s in preferred_unique if s in candidate]
    partial_detail: list[dict] = []
    missing: list[dict] = []
    for skill in required_unique:
        if skill in candidate:
            continue
        via, score = _best_fuzzy(skill, candidate)
        if via and skill not in partial:
            partial.append(skill)
            partial_detail.append({"skill": skill, "via": via,
                                   "similarity": round(score, 2)})
            continue
        missing.append({
            "skill": skill,
            "criticality": "High",
            "reason": "Required by the JD and not evidenced in the resume.",
            "weeks_to_learn": weeks_for(skill, taxonomy),
        })
    for skill in preferred_unique:
        if skill not in candidate:
            missing.append({
                "skill": skill,
                "criticality": "Medium",
                "reason": "Preferred by the JD and not evidenced in the resume.",
                "weeks_to_learn": weeks_for(skill, taxonomy),
            })
    critical_missing = [m["skill"] for m in missing if m["criticality"] == "High"]

    assert not (set(strong) & {m["skill"] for m in missing}), "gap invariant violated"
    assert not (set(partial) & {m["skill"] for m in missing}), "partial/missing overlap"
    return {
        "strong": strong,
        "partial": partial,
        "partial_detail": partial_detail,
        "missing": missing,
        "critical_missing": critical_missing,
    }
