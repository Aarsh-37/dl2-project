# 09 — Resume Optimize (v1, temp 0.4, constrained)

Propose a JD-targeted resume rewrite as JSON plus a markdown rendering. HARD RULES: do NOT invent employers, dates, degrees, skills, metrics, or projects. You MAY rephrase bullets using only metrics present in the original, inject JD keywords naturally, reorder sections for relevance, and add an "Areas to Upskill" section listing {critical_missing} (never as fake experience).

Original profile: {candidate_profile}
<JD>
{jd_text}
</JD>
Gaps: {skill_gap}

Return JSON only: {"summary": str, "skills": [], "experience": [], "projects": [], "education": [], "upskill": [], "markdown": str, "added_keywords": []}
The validator will reject any entity not traceable to the original — when in doubt, leave it out.
