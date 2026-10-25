"""Resume Analyzer wrapper: deterministic parse + taxonomy extract (LLM extract P2)."""
from __future__ import annotations

from app.tools import skill_extract


def analyze_resume(resume_text: str, taxonomy: dict | None = None) -> tuple[dict, list[dict]]:
    skills = skill_extract.extract_skills(resume_text or "", taxonomy) if taxonomy else []
    return {"skills": skills, "text": resume_text or ""}, []
