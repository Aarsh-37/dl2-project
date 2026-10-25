"""POST /mock/answer — on-demand mock evaluation (NOT a graph node).

v1 deterministic rubric: length + skill-term overlap + structure signals.
LLM evaluator lands in Phase 6; shape already matches the contract.
"""
from fastapi import APIRouter
from pydantic import BaseModel

from app.api.store import get_job

router = APIRouter()


class MockAnswer(BaseModel):
    job_id: str
    question_id: str = "q1"
    answer: str


def _score(answer: str, required: list[str]) -> tuple[dict, str]:
    words = answer.split()
    mentioned = [s for s in required if s.lower() in answer.lower()]
    tech = 2 + min(2, len(mentioned)) + (1 if len(words) > 80 else 0)
    tech = min(5, tech)
    relevance = 5 if mentioned else (3 if len(words) > 40 else 2)
    completeness = 5 if len(words) > 120 else (4 if len(words) > 60 else 3)
    communication = 5 if len(words) > 60 and "\n" in answer else 4
    confidence = 4 if ("trade-off" in answer.lower() or "metric" in answer.lower() or any(ch.isdigit() for ch in answer)) else 3
    feedback = (
        f"Matched {len(mentioned)}/{len(required)} JD skill terms"
        + (f" ({', '.join(mentioned[:3])})" if mentioned else "") + ". "
        "To score higher: add one concrete metric and name a trade-off."
    )
    return (
        {"Technical Accuracy": tech, "Relevance": relevance, "Completeness": completeness,
         "Communication": communication, "Confidence": confidence},
        feedback,
    )


@router.post("/mock/answer")
async def mock_answer(body: MockAnswer):
    if len(body.answer.strip()) < 10:
        return {"scores": {}, "feedback": "Write at least a sentence before submitting."}
    job = get_job(body.job_id)
    required = (job["result"].get("_required") or []) if job else []
    scores, feedback = _score(body.answer, required)
    return {"scores": scores, "feedback": feedback}
