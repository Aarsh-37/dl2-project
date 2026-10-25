"""Career Coach (LLM synthesizer, temp ~0.3): never overrides upstream facts."""
from __future__ import annotations

from app.core.llm import LLMError, get_llm


def coach_recommendations(ats: dict, gaps: dict, matches: list[dict] | None = None,
                          roadmap: dict | None = None,
                          validation: dict | None = None) -> tuple[str, list[dict]]:
    errors: list[dict] = []
    missing = [m["skill"] for m in (gaps or {}).get("missing", [])[:3]]
    base = (
        (f"Top fixes: {', '.join(missing)}. " if missing else "Strong match — polish metrics and JD keywords. ")
        + "Follow roadmap weeks + interview set above, built from your real gaps."
    )
    try:
        llm = get_llm("coach")
        if not llm.available:
            raise LLMError("No LLM key — template recommendations.")
        weeks = [w.get("focus", "") for w in (roadmap or {}).get("weeks", [])][:4]
        top_jobs = [f"{j.get('title')} @ {j.get('company')} ({j.get('match_pct')}%)"
                    for j in (matches or [])[:3] if j.get("source") != "link"]
        out = llm.invoke(
            "You are a direct, no-fluff career coach. Write 3 recommendations "
            "(2 lines each) grounded ONLY in these facts — each must name a specific "
            "skill, week, or action, never generic advice. Do not invent skills or scores. "
            "Plain text.\n"
            f"ATS: {ats.get('score')} ({ats.get('verdict')}). "
            f"Proven strengths: {ats.get('strengths', [])}. "
            f"Critical gaps: {missing}. "
            f"Roadmap order: {' → '.join(weeks) or 'see roadmap'}. "
            f"Resume validation: {(validation or {}).get('status', 'unknown')}. "
            f"Top job matches: {top_jobs or 'none yet'}."
        ).strip()
        if out:
            return out[:1000], errors
    except Exception as exc:  # noqa: BLE001
        errors.append({"node": "coach", "message": f"LLM coach skipped: {exc}"})
    return base, errors
