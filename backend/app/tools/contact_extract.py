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
    "summary": ("professional summary", "career summary", "summary", "profile",
                "objective", "about me"),
    "education": ("education", "academic", "qualification"),
    "experience": ("experience", "employment", "work history", "internship", "work experience"),
    "projects": ("project",),
    "skills": ("skill", "tech stack", "technologies", "technical",
               "competency", "competencies"),
    "certifications": ("certification", "certificate", "license", "licence",
                       "award", "awards", "honor", "honors"),
    "activities": ("co-curricular", "extracurricular", "activities", "activity",
                   "achievements", "accomplishments", "leadership", "interests", "hobbies"),
}

# Words that may surround a section keyword without changing its meaning
# ("Awards and Certifications", "Technical Skills Summary", "Key Projects").
_HEADING_FILLER = {
    "and", "&", "of", "the", "a", "an", "in", "for", "my", "work", "professional",
    "personal", "technical", "core", "key", "relevant", "other", "additional",
    "summary", "profile", "objective", "overview", "about", "me", "main",
}
_KW_TOKENS = {
    token
    for keywords in SECTION_KEYWORDS.values()
    for keyword in keywords
    for token in re.split(r"[^a-z]+", keyword)
    if token
}


def _heading_section(lowered: str) -> str | None:
    """Pick the section whose keyword appears furthest right (most specific)."""
    best: tuple[int, int, str] | None = None
    for section, keywords in SECTION_KEYWORDS.items():
        for keyword in keywords:
            idx = lowered.rfind(keyword)
            if idx >= 0:
                candidate = (idx, len(keyword), section)
                if best is None or candidate[:2] > best[:2]:
                    best = candidate
    return best[2] if best else None

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
    stripped = line.strip().rstrip(":").strip()
    if not stripped or len(stripped) > 45 or _BULLET.match(line):
        return None
    # Metadata continuations from PDF wrapping ("| Certificate", "(Remote)")
    # are body text, never section headings.
    if stripped.startswith(("|", "\u2022", "\u00b7", "\u2013", "\u2014", "(")):
        return None
    if not re.search(r"[A-Za-z]", stripped):
        return None
    lowered = stripped.lower()
    section = _heading_section(lowered)
    if section is None:
        return None
    if stripped.isupper() or line.strip().endswith(":"):
        return section
    # A real heading is made of section words/filler only. This keeps
    # "Academic Projects" a heading while "Data Engineering Virtual
    # Internship" (a certificate name) stays in its current section.
    tokens = re.findall(r"[a-z]+", lowered)
    if not tokens or len(tokens) > 7:
        return None
    for token in tokens:
        if token in _HEADING_FILLER or token in _KW_TOKENS:
            continue
        if any(len(token) >= 4 and len(kw) >= 4
               and (token.startswith(kw) or kw.startswith(token))
               for kw in _KW_TOKENS):
            continue
        return None
    return section


def is_heading(line: str) -> str | None:
    """Public heading check (section name or None) for sibling exporters."""
    return _is_heading(line)


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
