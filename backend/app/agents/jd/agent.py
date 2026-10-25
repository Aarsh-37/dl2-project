"""JD Analyzer: deterministic parse first, LLM fills gaps (temp ~0.15).

Output: {role, required_skills, preferred_skills, responsibilities,
         experience, education, keywords, domain}. Never raises — on LLM
failure returns deterministic extraction + error note.
"""
from __future__ import annotations

from app.core.llm import LLMError, get_llm, parse_json_block
from app.tools import jd_parser, skill_extract


def analyze_jd(jd_text: str, taxonomy: dict | None = None) -> tuple[dict, list[dict]]:
    errors: list[dict] = []
    parsed = jd_parser.parse_jd(jd_text or "")
    sections = parsed.get("sections", {})
    if taxonomy:
        required = skill_extract.extract_skills(sections.get("required", ""), taxonomy)
        preferred = skill_extract.extract_skills(sections.get("preferred", ""), taxonomy)
        if not required:  # plain-text JD fallback
            required = skill_extract.extract_skills(parsed.get("text", ""), taxonomy)
            preferred = []
    else:
        required, preferred = [], []

    profile: dict = {
        "role": sections.get("required", "").split("\n")[0][:120] if sections.get("required") else "",
        "required_skills": required,
        "preferred_skills": preferred,
        "responsibilities": [l.strip() for l in sections.get("responsibilities", "").split("\n") if l.strip()][:8],
        "experience": sections.get("experience", ""),
        "education": sections.get("education", ""),
        "keywords": sorted(set(required + preferred)),
        "domain": "",
    }

    # LLM assist: role/domain/responsibilities cleanup only — skills stay deterministic.
    try:
        llm = get_llm("jd")
        if not llm.available:
            raise LLMError("No LLM key — deterministic JD profile.")
        prompt = (
            "Extract a hiring-JD profile as JSON only: "
            '{"role": str, "domain": str, "responsibilities": [str max 8]}. '
            "Role = job title copied from the JD (empty string if absent). "
            "Domain = industry/field. Responsibilities = verbatim or lightly "
            "normalised duties; never invent. No extra text.\n"
            f"<JD>{(jd_text or '')[:4000]}</JD>"
        )
        patch = parse_json_block(llm.invoke(prompt))
        if isinstance(patch, dict):
            role = str(patch.get("role") or "").strip()
            if role and len(role) <= 80 and "{" not in role and "json" not in role.lower():
                profile["role"] = role
            domain = str(patch.get("domain") or "").strip()
            if domain and len(domain) <= 60 and "{" not in domain and "json" not in domain.lower():
                profile["domain"] = domain
            if isinstance(patch.get("responsibilities"), list):
                cleaned: list[str] = []
                for item in patch["responsibilities"][:8]:
                    text = str(item).strip(" .;-*")
                    if 8 <= len(text) <= 200 and text not in cleaned:
                        cleaned.append(text)
                if cleaned:
                    profile["responsibilities"] = cleaned
    except Exception as exc:  # noqa: BLE001 — fallback is the contract
        errors.append({"node": "jd_analyzer", "message": f"LLM assist skipped: {exc}"})
    return profile, errors
