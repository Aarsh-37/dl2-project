# 01 — Resume Extract (v1, temp 0.1)

Extract the resume below into JSON. Skills must be atomic (Docker, not DevOps). Years as float. No invention — use null when missing.

<RESUME>
{resume_text}
</RESUME>

Return JSON only: {"candidate": {"name": str|null, "email": str|null, "phone": str|null, "links": []}, "skills": [], "experience": [{"title": str, "company": str|null, "years": float|null, "bullets": []}], "projects": [{"name": str, "stack": [], "bullets": []}], "education": [], "certifications": []}
On schema failure the caller retries once with: "Return valid JSON only, same schema."
