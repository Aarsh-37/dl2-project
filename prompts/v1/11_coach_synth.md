# 11 — Coach Synthesize (v1, temp 0.4)

Synthesize — do NOT override — the upstream results into career recommendations: top-3 priority fixes, suggested prep timeline pointing at roadmap weeks + interview sets, and next job-search filters. If upstream facts conflict, report the conflict instead of guessing.

ATS: {ats_result}
Gaps: {skill_gap}
Roadmap: {roadmap}
Interview: {interview_questions}
Matches: {job_matches}

Return JSON only: {"priorities": [], "timeline": str, "prep_plan": str, "job_filters": {}, "career_recommendations": str}
