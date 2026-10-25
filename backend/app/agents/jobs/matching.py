"""Job Matching (deterministic). LLM intentionally does NOT contribute here —
rationale lines are computed from the match itself, no provider calls."""


def match_jobs(jobs: list[dict], profile: dict) -> list[dict]:
    skills = set((profile or {}).get("technical", []))
    ranked = []
    for job in jobs or []:
        if job.get("source") == "link":
            ranked.append(job)
            continue
        text = f"{job.get('title', '')} {job.get('description', '')}"
        matched = sorted({s for s in skills if s.lower() in text.lower()})
        pct = round(100 * len(matched) / max(len(skills), 1), 1) if skills else 0
        ranked.append({**job, "match_pct": pct, "matched_skills": matched})
    ranked.sort(key=lambda j: j.get("match_pct", 0), reverse=True)
    return ranked


def explain_matches(matches: list[dict], errors: list[dict] | None = None) -> list[dict]:
    """Deterministic one-liner only — no LLM contribution by design."""
    for job in matches or []:
        if job.get("source") == "link":
            continue
        job.setdefault("why", f"Matches {len(job.get('matched_skills', []))} profile skills.")
    return matches or []
