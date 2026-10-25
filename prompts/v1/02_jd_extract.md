# 02 — JD Extract (v1, temp 0.1)

Extract job requirements into JSON. Split skills into required (must-have language) vs preferred (nice-to-have language). No invention — use [] when absent.

<JD>
{jd_text}
</JD>

Return JSON only: {"role": str, "required_skills": [], "preferred_skills": [], "responsibilities": [], "experience": [], "education": [], "keywords": [], "domain": str}
