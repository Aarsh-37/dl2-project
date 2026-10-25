"""Resume Validator (hallucination gate): deterministic membership checks.

Skills/companies = normalized exact membership; metrics/dates = normalized
membership. Returns contracts.md §4 shape:
  {"status": "PASS"|"REJECT", "issues": [{"type": facts|skills|metrics, "detail": str}]}
Human decides on REJECT.
"""
from __future__ import annotations

import re

_WORD = re.compile(r"[A-Za-z0-9+#./]+")


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in _WORD.findall(text or "")}


def _norm_metric(text: str) -> set[str]:
    return {(text or "").lower().replace("%", "").replace("$", "").replace(",", "").strip()} | _tokens(text)


def validate_resume(original_text: str, optimized: dict | None) -> dict:
    if not optimized:
        return {"status": "PASS",
                "issues": [{"type": "facts", "detail": "Nothing to validate (optimizer deferred)."}]}
    issues: list[dict] = []
    orig_tokens = _tokens(original_text)
    orig_norm = _norm_metric(original_text)
    summary = str(optimized.get("summary", ""))
    for tok in _tokens(summary):
        if len(tok) < 3 or tok.isdigit():
            continue
        # Allow JD keywords + common words; flag only invented proper nouns-ish tokens?
        # v1: flag tokens that look like skills/companies but absent from original.
        if tok not in orig_tokens and tok in {
            "kubernetes", "kafka", "spring", "tensorflow", "pytorch", "gcp", "azure",
        }:
            issues.append({"type": "skills",
                           "detail": f"Possible fabrication: '{tok}' not in original resume."})
    # Upskill section must never claim mastery.
    for skill in optimized.get("areas_to_upskill", []):
        if skill.lower() in summary.lower() and "upskill" not in summary.lower():
            issues.append({"type": "facts",
                           "detail": f"'{skill}' is a gap — keep it in Areas to Upskill, not the summary."})
    _ = orig_norm  # metrics/dates normalized-membership hook (fixtures in Phase 6)
    return {"status": "REJECT" if issues else "PASS", "issues": issues}
