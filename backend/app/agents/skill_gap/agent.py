"""Skill Gap agent: thin wrapper over deterministic gap_service (LLM validates later)."""
from __future__ import annotations

from app.services.gap_service import compute_gaps


def analyze_gaps(candidate: list[str], required: list[str], preferred: list[str],
                 taxonomy: dict | None = None) -> tuple[dict, list[dict]]:
    return compute_gaps(candidate, required, preferred, taxonomy), []
