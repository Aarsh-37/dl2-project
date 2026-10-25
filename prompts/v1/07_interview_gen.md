# 07 — Interview Generate (v1, temp 0.7)

You are the hiring manager at {company} for {role}. Using the JD, resume, and gaps below, generate 12 technical (4 Easy / 4 Medium / 4 Hard, ~30% company-specific) + 8 HR questions. Ground every resume-based question in the actual resume — never reference employers the candidate never had.

<JD>
{jd_text}
</JD>
<RESUME>
{resume_text}
</RESUME>
Gaps: {skill_gap}

Return JSON only: {"technical": [{"q": str, "difficulty": str, "why_asked": str, "ideal_answer": str, "key_points": [], "follow_up": str}], "resume_based": [], "project_based": [], "hr": [], "follow_ups": []}
Ideal answers ~150 words; technical answers include code where apt; HR answers use STAR.
