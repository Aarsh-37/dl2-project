# 10 — Job Explain (v1, temp 0.3, top-30 only)

Explain in 2–3 lines why this job fits (or doesn't fit) the candidate, given the DETERMINISTIC match breakdown. Do not change the score. Only jobs with real URLs from the job APIs are ever explained — never invent postings.

Candidate: {candidate_profile}
Job: {job_json}
Deterministic breakdown: {match_breakdown}

Return JSON only: {"explanation": str, "fit": "good|stretch|poor"}
