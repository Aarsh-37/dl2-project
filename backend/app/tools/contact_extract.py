"""Contact + section extraction from resume text. Deterministic, no LLM.

Sections follow the export order: education, experience, projects, skills,
certifications, activities (co-/extra-curricular). Anything before the first
recognized heading is the header block (name + contact lines).
"""
from __future__ import annotations

import re

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE = re.compile(r"\+?\d[\d\s\-()]{7,}\d")
GITHUB = re.compile(r"(?:https?://)?(?:www\.)?github\.com/([A-Za-z0-9_.-]+)", re.I)
LINKEDIN = re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/in/([A-Za-z0-9_.-]+/?)", re.I)

SECTION_KEYWORDS: dict[str, tuple[str, ...]] = {
    "education": ("education", "academic", "qualification"),
    "experience": ("experience", "employment", "work history", "internship", "work experience"),
    "projects": ("project",),
    "skills": ("skill", "tech stack", "technologies", "technical"),
    "certifications": ("certification", "certificate", "license", "licence"),
    "activities": ("co-curricular", "extracurricular", "activities", "activity",
                   "achievements", "accomplishments", "leadership", "interests", "hobbies"),
}

_BULLET = re.compile(r"^(\s*[-*•>]|\s*\d+[.)])\s+")


def extract_contact(text: str) -> dict:
    """Return {email, phone, github, linkedin} — "" when absent, never raises."""
    text = text or ""
    emails = EMAIL.findall(text)
    phones = PHONE.findall(text)
    gh = GITHUB.search(text)
    li = LINKEDIN.search(text)
    return {
        "email": emails[0] if emails else "",
        "phone": re.sub(r"\s+", " ", phones[0]).strip() if phones else "",
        "github": f"github.com/{gh.group(1)}" if gh else "",
        "linkedin": f"linkedin.com/in/{li.group(1)}" if li else "",
    }


def _is_heading(line: str) -> str | None:
    stripped = line.strip().rstrip(":")
    if not stripped or len(stripped) > 45 or _BULLET.match(line):
        return None
    if not re.search(r"[A-Za-z]", stripped):
        return None
    lowered = stripped.lower()
    for section, keywords in SECTION_KEYWORDS.items():
        if any(kw in lowered for kw in keywords):
            if stripped.isupper() or stripped.istitle() or line.strip().endswith(":") \
                    or lowered in keywords or any(lowered == kw or lowered.startswith(kw + " ")
                                                 for kw in keywords):
                return section
    return None


def split_sections(text: str) -> dict[str, list[str]]:
    """Split resume text into {header, education, experience, projects, skills,
    certifications, activities}. Unrecognized blocks stay with the current
    section; text before the first heading goes to header."""
    sections: dict[str, list[str]] = {"header": []}
    current = "header"
    for raw in (text or "").split("\n"):
        line = raw.rstrip()
        if not line.strip():
            continue
        heading = _is_heading(line)
        if heading:
            current = heading
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line.strip())
    return sections


def extract_name(header: list[str]) -> str:
    """First short line of the header block; 'Candidate' when unsure."""
    for line in header:
        clean = re.sub(r"[_*`#]", "", line).strip()
        if clean and len(clean) <= 60 and not EMAIL.search(clean) and not _BULLET.match(line):
            return clean
    return "Candidate"
