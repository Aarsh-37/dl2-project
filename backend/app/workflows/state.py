"""CareerState — single source of truth (frozen keys per contracts.md)."""
from __future__ import annotations

import operator
from typing import Annotated, TypedDict


class CareerState(TypedDict, total=False):
    user_id: str
    hours_per_day: int
    resume_text: str
    resume_profile: dict
    job_description: str
    jd_profile: dict
    candidate_profile: dict
    ats_result: dict
    skill_gap: dict
    roadmap: dict
    interview_questions: dict
    interview_session: dict
    optimized_resume: dict | None
    validation_result: dict
    jobs: list
    job_matches: list
    career_recommendations: str
    status: str
    agent_trace: list  # verbose log of LLM calls (node/provider/model/latency/mode)
    errors: Annotated[list, operator.add]  # reducer — parallel nodes concat safely
    # Internal scratch (underscore keys are stripped from API payloads but MUST
    # be declared or LangGraph drops them from node returns).
    _required: list
    _preferred: list
    _candidate: list
