"""Deterministic JD parsing: clean + split into requirement sections. No LLM, no DB."""
import re

from app.utils.text_clean import clean_text

_HEADING = re.compile(r"^#{1,4}\s*(.+?)\s*$")

_SECTION_RULES = (
    ("required", re.compile(r"requir|must|need|essential|mandatory", re.I)),
    ("preferred", re.compile(r"prefer|nice|bonus|good to have|optional|plus", re.I)),
    ("responsibilities", re.compile(r"responsib|you.?ll|duties|what you", re.I)),
    ("experience", re.compile(r"experience", re.I)),
    ("education", re.compile(r"education|qualification", re.I)),
)


def split_sections(text: str) -> dict[str, str]:
    """Split markdown into heading -> body. Non-heading text goes to 'intro'."""
    sections: dict[str, str] = {}
    current = "intro"
    buf: list[str] = []
    for line in text.split("\n"):
        match = _HEADING.match(line.strip())
        if match:
            sections[current] = "\n".join(buf).strip()
            current = match.group(1)
            buf = []
        else:
            buf.append(line)
    sections[current] = "\n".join(buf).strip()
    return sections


def classify_sections(sections: dict[str, str]) -> dict[str, str]:
    """Map raw headings onto required/preferred/responsibilities/experience/education."""
    grouped: dict[str, list[str]] = {
        "required": [], "preferred": [], "responsibilities": [],
        "experience": [], "education": [], "other": [],
    }
    for heading, body in sections.items():
        if heading == "intro" or not body:
            continue
        placed = False
        for key, pattern in _SECTION_RULES:
            if pattern.search(heading):
                grouped[key].append(body)
                placed = True
                break
        if not placed:
            grouped["other"].append(body)
    return {key: "\n".join(parts).strip() for key, parts in grouped.items()}


def parse_jd(text: str) -> dict:
    """Parse raw JD text -> {"text", "sections"}. Sections may be empty strings."""
    cleaned = clean_text(text)
    return {"text": cleaned, "sections": classify_sections(split_sections(cleaned))}
