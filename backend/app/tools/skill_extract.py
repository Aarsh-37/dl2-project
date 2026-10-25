"""Taxonomy-driven skill extraction. Deterministic, no LLM, no DB.

Loads data/skill_taxonomy.csv once (pass the dict around afterwards).
Matching is case-insensitive with code-aware boundaries so "C" never matches
"C++" and "SQL" never matches "SQLite". Simple plural tolerance ("REST APIs"
matches the "REST API" term) for terms longer than 2 chars.
"""
import csv
import re
from pathlib import Path

_BOUND_LEFT = r"(?<![A-Za-z0-9_+#./])"
_BOUND_RIGHT = r"(?![A-Za-z0-9_+#])"
_PLURAL_OK = re.compile(r"^.{3,}[^sS+./]$")


def load_taxonomy(csv_path: str | Path) -> dict:
    """Return {"terms": {term_lower: canonical}, "category": {canonical: category}}."""
    terms: dict[str, str] = {}
    category: dict[str, str] = {}
    with open(csv_path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            name = (row.get("name") or "").strip()
            alias_of = (row.get("alias_of") or "").strip()
            cat = (row.get("category") or "").strip()
            if not name:
                continue
            if alias_of:
                terms[name.lower()] = alias_of
            else:
                terms[name.lower()] = name
                if cat:
                    category[name] = cat
    return {"terms": terms, "category": category}


def _pattern_for(term: str) -> "re.Pattern[str]":
    plural = "s?" if _PLURAL_OK.match(term) else ""
    return re.compile(_BOUND_LEFT + re.escape(term) + plural + _BOUND_RIGHT, re.IGNORECASE)


def contains_term(text: str, term: str) -> bool:
    """Boundary-aware presence check ("Go" never matches "Django").

    Same matching rules as extract_skills, for callers (ATS keyword scorer)
    that test one canonical term at a time.
    """
    if not text or not term:
        return False
    return bool(_pattern_for(term.strip()).search(text))


def _resolve(matched: str, terms: dict[str, str]) -> str | None:
    key = matched.lower()
    if key in terms:
        return terms[key]
    if key.endswith("s") and key[:-1] in terms:
        return terms[key[:-1]]
    return None


def normalize_skill(name: str, taxonomy: dict) -> str | None:
    """Map an alias or variant to its canonical skill name. None if unknown."""
    if not name:
        return None
    return _resolve(name.strip(), taxonomy["terms"])


def extract_skills(text: str, taxonomy: dict) -> list[str]:
    """Return sorted unique canonical skills found in text."""
    if not text:
        return []
    terms = taxonomy["terms"]
    found: set[str] = set()
    for term in sorted(terms, key=len, reverse=True):
        match = _pattern_for(term).search(text)
        if match:
            canonical = _resolve(match.group(0), terms)
            if canonical:
                found.add(canonical)
    return sorted(found)


def category_of(skill: str, taxonomy: dict) -> str | None:
    return taxonomy["category"].get(skill)
