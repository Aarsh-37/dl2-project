"""Interview Generator (temp ~0.7): RAG-first prep, LLM only fills gaps.

Order per skill: your PDF pairs -> bank questions -> ONE short targeted LLM
call for still-uncovered skills -> deterministic templates. The LLM fires
only when retrieval genuinely misses, so prep is fast AND grounded in your
material. A sanitizer guarantees shape + per-skill coverage + caps.
"""
from __future__ import annotations

from app.core.llm import LLMError, get_llm, llm_json
from app.services import kb_service as kb

MAX_TECH, MAX_HR = 12, 8
DIFFICULTIES = {"Easy", "Medium", "Hard"}


def _template_q(skill: str, known: bool, kind: str = "skill") -> dict:
    if kind == "project":
        return {
            "category": "project", "skill": skill,
            "q": f"Walk me through a project where {skill} was central — architecture, your role, hardest bug.",
            "difficulty": "Medium",
            "why_asked": f"Project depth in resume: {skill}",
            "ideal_answer": ("Set the stage (goal/stack), your exact contribution, the toughest bug "
                             "and how you fixed it, one measurable outcome."),
            "key_points": ["Architecture", "Your contribution", "Hardest bug + fix", "Metric"],
            "follow_up": f"If you rebuilt that {skill} project today, what would you change?",
        }
    if kind == "architecture":
        return {
            "category": "architecture", "skill": skill,
            "q": f"How would you scale a {skill} system you built from hundreds to millions of users?",
            "difficulty": "Hard",
            "why_asked": f"System thinking beyond syntax: {skill}",
            "ideal_answer": ("Stateless services behind a load balancer, caching hot paths, read replicas, "
                             "async queues for writes, CDN for static, load-test before claiming numbers."),
            "key_points": ["Bottleneck first", "Caching", "Async + CDN", "Trade-offs"],
            "follow_up": "What breaks first in your design, and how would you detect it?",
        }
    return {
        "category": "skill", "skill": skill,
        "q": f"Explain how you have used {skill} in a project (or how you would approach learning it).",
        "difficulty": "Medium" if known else "Easy",
        "why_asked": f"{'Grounded in resume' if known else 'Tests the gap'}: {skill}",
        "ideal_answer": (f"Describe a concrete {skill} task: context, approach, trade-off, "
                         "and one measurable outcome."),
        "key_points": ["Concrete example", "Trade-off named", "Measurable outcome"],
        "follow_up": f"What would break first if your {skill} solution had 100x load?",
    }


def _sanitize_interview(data: dict, required: list[str], candidate: list[str],
                        gaps: dict | None) -> dict:
    """Enforce item shape, difficulty values, caps, and per-skill coverage."""
    def clean(item: dict, default_diff: str = "Medium") -> dict:
        diff = item.get("difficulty", default_diff)
        keys = [str(k)[:250] for k in (item.get("key_points") or [])][:5] or ["Concrete example"]
        return {
            "category": str(item.get("category", "skill"))[:20],
            "skill": str(item.get("skill", ""))[:40],
            "q": str(item.get("q", ""))[:500],
            "difficulty": diff if diff in DIFFICULTIES else default_diff,
            "why_asked": str(item.get("why_asked", ""))[:250],
            "ideal_answer": str(item.get("ideal_answer", ""))[:800],
            "key_points": keys,
            "follow_up": str(item.get("follow_up", "What would you do differently?"))[:250],
        }

    tech = [clean(t) for t in (data.get("technical") or []) if isinstance(t, dict) and t.get("q")]
    hr = [clean(h, "Easy") for h in (data.get("hr") or []) if isinstance(h, dict) and h.get("q")]
    covered = {s for t in tech for s in (required or []) if s.lower() in (t["q"] + t["why_asked"]).lower()}
    for skill in (required or [])[:8]:
        if skill not in covered and len(tech) < MAX_TECH:
            tech.append(_template_q(skill, skill in (candidate or [])))
            covered.add(skill)
    # Pad to full depth so LLM shortfalls never thin the prep set.
    pool = list(dict.fromkeys((required or []) + [m["skill"] for m in (gaps or {}).get("missing", [])]))
    kinds = ("project", "architecture", "skill")
    ki = 0
    while len(tech) < MAX_TECH and pool:
        skill = pool[len(tech) % len(pool)]
        tech.append(_template_q(skill, skill in (candidate or []), kinds[ki % 3]))
        ki += 1
    if len(hr) < MAX_HR:
        bank_hr = kb.get_questions([], limit=MAX_HR)
        seen = {h["q"] for h in hr}
        for t in bank_hr:
            if len(hr) >= MAX_HR:
                break
            if t["q"] not in seen:
                hr.append(clean({
                    "category": "behavioral", "q": t["q"], "difficulty": t.get("difficulty", "Easy"),
                    "why_asked": "Behavioral signal", "ideal_answer": t.get("ideal_answer", ""),
                    "key_points": t.get("key_points", []) or ["STAR"],
                    "follow_up": "What would you do differently?"}, "Easy"))
    return {"technical": tech[:MAX_TECH], "hr": hr[:MAX_HR]}


def _rag_item(pair: dict, known: bool, bank_hit: dict | None = None) -> dict:
    """Turn a retrieved PDF pair into an interview item (zero LLM cost)."""
    return {
        "category": "skill", "skill": pair.get("skill", ""),
        "q": pair["q"],
        "difficulty": (bank_hit or {}).get("difficulty", "Medium"),
        "why_asked": (f"From your prep material "
                      f"({pair.get('source', '').replace('.pdf', '')}"
                      f"{' p.' + str(pair['page']) if pair.get('page') else ''}): "
                      f"{pair.get('skill', '')}"),
        "ideal_answer": pair["a"],
        "key_points": (bank_hit or {}).get("key_points", []) or ["Concrete example"],
        "follow_up": (f"Go deeper: what trade-off applies when using "
                      f"{pair.get('skill', 'this')} at scale?"),
    }


def _rag_hr_item(pair: dict) -> dict:
    return {
        "category": "behavioral", "skill": "General",
        "q": pair["q"], "difficulty": "Medium",
        "why_asked": (f"From your HR prep material "
                      f"({pair.get('source', '').replace('.pdf', '')}"
                      f"{' p.' + str(pair['page']) if pair.get('page') else ''})"),
        "ideal_answer": pair["a"],
        "key_points": ["STAR"],
        "follow_up": "What would you do differently?",
    }


def _short_tech_prompt(skills: list[str], candidate: list[str], role: str) -> str:
    return (
        "You are a senior hiring manager. Generate interview questions as JSON only: "
        '{"technical": [{"category": "skill", "skill": str, "q": str, '
        '"difficulty": "Easy|Medium|Hard", "why_asked": str, '
        '"ideal_answer": str (2-4 specific sentences), "key_points": [3 str], '
        '"follow_up": str}]}. '
        f"Role: {role or 'as per JD'}. Generate up to 3 questions EACH for these "
        f"skills only: {', '.join(skills)}. Candidate knows: "
        f"{', '.join((candidate or [])[:10]) or 'basics'}. Every question must name "
        "its skill. Specific, non-generic, JSON only."
    )


def generate_interview(required: list[str], candidate: list[str], gaps: dict | None = None,
                       role: str = "", resume_text: str = "") -> tuple[dict, list[dict]]:
    """RAG-first interview prep: your PDFs answer first, Ollama fills gaps.

    Order per skill: PDF pairs -> bank questions -> ONE short targeted LLM
    call for still-uncovered skills -> deterministic templates. The LLM only
    fires when retrieval genuinely misses, so prep is fast AND grounded.
    """
    errors: list[dict] = []
    missing = [m["skill"] for m in (gaps or {}).get("missing", [])[:4]]
    skills = list(dict.fromkeys((required or []) + missing))
    # Bank index for difficulty/key-point enrichment of RAG pairs.
    bank = kb.get_questions(skills, limit=24)
    bank_by_q = {str(b.get("q", ""))[:80].lower(): b for b in bank}

    tech: list[dict] = []
    covered: set[str] = set()
    rag_pairs = kb.get_rag_questions(skills, per_skill=2)
    for pair in rag_pairs:
        tech.append(_rag_item(pair, pair["skill"] in (candidate or []),
                              bank_by_q.get(pair["q"][:80].lower())))
        covered.add(pair["skill"])
    rag_hr_pairs = kb.get_rag_hr_questions(limit=8)
    for b in bank:
        if len([t for t in tech if t["skill"] == b.get("skill")]) >= 2:
            continue
        if any(b.get("q", "") == t["q"] for t in tech):
            continue
        tech.append({
            "category": "skill", "skill": b.get("skill", ""), "q": b.get("q", ""),
            "difficulty": b.get("difficulty", "Medium"),
            "why_asked": f"From question bank: {b.get('skill', '')}",
            "ideal_answer": b.get("ideal_answer", ""),
            "key_points": b.get("key_points", []) or ["Concrete example"],
            "follow_up": f"Go deeper: what trade-off did you make with {b.get('skill', 'this')}?",
        })
        covered.add(b.get("skill", ""))

    hr: list[dict] = []
    for pair in rag_hr_pairs:
        hr.append(_rag_hr_item(pair))
    for b in kb.get_questions([], limit=8):
        if len(hr) >= MAX_HR:
            break
        if any(b.get("q", "") == h["q"] for h in hr):
            continue
        hr.append({
            "category": "behavioral", "q": b.get("q", ""),
            "difficulty": b.get("difficulty", "Easy"),
            "why_asked": "Behavioral signal",
            "ideal_answer": b.get("ideal_answer", ""),
            "key_points": b.get("key_points", []) or ["STAR"],
            "follow_up": "What would you do differently?",
        })

    sources: list[dict] = []
    seen_src: set[str] = set()
    for pair in rag_pairs + rag_hr_pairs:
        key = (pair.get("source", ""), pair.get("skill", ""))
        if key not in seen_src:
            seen_src.add(key)
            sources.append({"source": key[0], "skill": key[1], "page": pair.get("page")})

    uncovered = [s for s in skills[:8] if s not in covered]
    if uncovered:
        try:
            llm = get_llm("interview")
            if not llm.available:
                raise LLMError("No LLM key — templates cover the rest.")
            data, rep_errs = llm_json("interview", _short_tech_prompt(uncovered, candidate, role))
            errors.extend(rep_errs)
            extra = data.get("technical", []) if isinstance(data, dict) else []
            tech.extend(extra)
        except Exception as exc:  # noqa: BLE001
            errors.append({"node": "interview",
                           "message": f"Targeted LLM fill skipped: {exc}"})
    merged = _sanitize_interview({"technical": tech, "hr": hr}, required, candidate, gaps)
    merged["sources"] = sources
    return merged, errors
