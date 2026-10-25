# 05 — Gap Label (v1, temp 0.3)

Given normalized candidate skills and JD required/preferred skills, label each JD skill as strong (evidenced), partial (mentioned, no depth), or missing. For each missing skill give criticality High (blocks responsibilities) / Medium / Low (nice-to-have), a one-line reason, and weeks_to_learn for the given level.

Candidate: {candidate_profile}
JD: {jd_profile}
Level: {level} (fresher|experienced)

Return JSON only: {"strong": [], "partial": [], "missing": [{"skill": str, "criticality": str, "reason": str, "weeks_to_learn": int}], "critical_missing": []}
Invariant: no skill may appear in both strong and missing.
