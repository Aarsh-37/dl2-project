"""Candidate Profile Normalizer — downstream single source of truth.

Deterministic taxonomy normalize (JS->JavaScript); LLM assist optional.
"""
from __future__ import annotations

from app.core.llm import LLMError, get_llm
from app.tools import skill_extract


def normalize_profile(resume_text: str, taxonomy: dict | None = None) -> tuple[dict, list[dict]]:
    errors: list[dict] = []
    skills = skill_extract.extract_skills(resume_text or "", taxonomy) if taxonomy else []
    profile: dict = {
        "technical": skills,
        "soft": [],
        "experience": [],
        "projects": [],
        "education": [],
        "strengths": skills[:5],
        "preferences": {},
    }
    try:
        llm = get_llm("extract")
        if not llm.available:
            raise LLMError("No LLM key — taxonomy-only profile.")
        out = llm.invoke(
            "List only interpersonal/soft skills from this resume (e.g. communication, "
            "teamwork, leadership). Never list programming languages, frameworks, tools, "
            "degrees or job titles. Reply as comma-separated words only, else 'none'.\n"
            f"<RESUME>{(resume_text or '')[:3000]}</RESUME>"
        ).strip()
        if out.lower() != "none":
            technical = {s.lower() for s in skills}
            soft: list[str] = []
            for raw_word in out.replace("\n", ",").split(","):
                word = raw_word.strip(" .;-*")
                if not (2 <= len(word) <= 30) or word.lower() in technical:
                    continue
                if not any(ch.isalpha() for ch in word):
                    continue
                if word.lower() not in {s.lower() for s in soft}:
                    soft.append(word)
            profile["soft"] = soft[:8]
    except Exception as exc:  # noqa: BLE001
        errors.append({"node": "profile", "message": f"LLM assist skipped: {exc}"})
    return profile, errors
