# 03 — Profile Normalize (v1, temp 0.2)

Merge the resume profile (plus history if provided) into one normalized candidate profile. Normalize aliases using the taxonomy (JS→JavaScript, Postgres→PostgreSQL, K8s→Kubernetes). Never add skills not present in the input.

Input profile: {resume_profile}
Return JSON only: {"technical": [], "soft": [], "experience": [], "projects": [], "education": [], "strengths": [], "preferences": {}}
