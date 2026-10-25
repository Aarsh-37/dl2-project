"""Save/load core outputs. Every query filters by user_id.

The service-role/direct connection bypasses RLS (database.md §5), so the
filter below IS the authorization — never query these tables without it.
result_json follows contracts.md §5.1. Embeddings stay NULL until Phase 2
backfill. Storage-file deletion happens in the API layer (delete first).
"""
import hashlib
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.core import (
    Analysis,
    DocumentChunk,
    JdSkill,
    JobDescription,
    Resume,
    ResumeSkill,
    Skill,
    SkillGap,
)
from app.utils.text_clean import chunk_text


def _skill_id_map(db: Session) -> dict[str, object]:
    rows = db.execute(select(Skill.id, Skill.name)).all()
    return {name: sid for sid, name in rows}


def save_analysis(
    db: Session,
    *,
    user_id: str,
    resume_file_url: str,
    resume_text: str,
    jd_text: str,
    company: str = "",
    role: str = "",
    level: str = "fresher",
    hours_per_day: int = 3,
    candidate_skills: list[str],
    required: list[str],
    preferred: list[str],
    ats: dict,
    gaps: dict,
    full_result: dict | None = None,
    analysis_id: str | None = None,
) -> Analysis:
    """Persist one full core run. Returns the Analysis row (id IS job_id)."""
    skill_ids = _skill_id_map(db)
    missing_taxonomy = (
        set(candidate_skills) | set(required) | set(preferred)
    ) - set(skill_ids)
    if missing_taxonomy:
        for s in missing_taxonomy:
            db.add(Skill(name=s))
        db.flush()
        skill_ids = _skill_id_map(db)

    resume = Resume(
        user_id=user_id,
        file_url=resume_file_url,
        raw_text=resume_text,
        sha256=hashlib.sha256(resume_text.encode()).hexdigest(),
        parsed_json={"skills": candidate_skills},
    )
    jd = JobDescription(user_id=user_id, raw_text=jd_text, company=company or None, role=role or None)
    db.add_all([resume, jd])
    db.flush()

    for skill in candidate_skills:
        db.add(ResumeSkill(resume_id=resume.id, skill_id=skill_ids[skill]))
    for skill in required:
        db.add(JdSkill(jd_id=jd.id, skill_id=skill_ids[skill], requirement="required"))
    for skill in preferred:
        if skill not in required:
            db.add(JdSkill(jd_id=jd.id, skill_id=skill_ids[skill], requirement="preferred"))

    for idx, chunk in enumerate(chunk_text(resume_text)):
        db.add(DocumentChunk(owner_type="resume", owner_id=resume.id,
                             section="full", chunk_index=idx, text=chunk))
    for idx, chunk in enumerate(chunk_text(jd_text)):
        db.add(DocumentChunk(owner_type="jd", owner_id=jd.id,
                             section="full", chunk_index=idx, text=chunk))

    status_lookup = {"strong": "strong", "partial": "partial"}
    for item in gaps.get("missing", []):
        status = "critical_missing" if item["criticality"] == "High" else "missing"
        status_lookup[item["skill"]] = status

    # Store the full §5.1 result when the caller has it (roadmap, interview,
    # coach included); internal `_` keys are stripped like the API payload.
    if full_result:
        stored = {k: v for k, v in full_result.items() if not k.startswith("_")}
    else:
        stored = {"ats_result": ats, "skill_gap": gaps, "errors": []}
    analysis = Analysis(
        id=uuid.UUID(analysis_id) if analysis_id else uuid.uuid4(),
        user_id=user_id, resume_id=resume.id, jd_id=jd.id,
        company=company or None, role=role or None,
        level=level, hours_per_day=hours_per_day,
        status="done",
        result_json=stored,
        ats_score=int(ats.get("score", 0)),
    )
    db.add(analysis)
    db.flush()

    for skill in gaps.get("strong", []):
        db.add(SkillGap(analysis_id=analysis.id, skill_id=skill_ids[skill],
                        status="strong", reason="Matched required skill."))
    for skill in gaps.get("partial", []):
        db.add(SkillGap(analysis_id=analysis.id, skill_id=skill_ids[skill],
                        status="partial", reason="Matched preferred skill."))
    for item in gaps.get("missing", []):
        db.add(SkillGap(analysis_id=analysis.id, skill_id=skill_ids[item["skill"]],
                        status=status_lookup[item["skill"]],
                        reason=item.get("reason"),
                        weeks_to_learn=item.get("weeks_to_learn")))
    db.commit()
    db.refresh(analysis)
    return analysis


def load_analysis(db: Session, *, user_id: str, job_id: str) -> dict | None:
    """Return result_json for this user's analysis, else None. user_id enforced."""
    row = db.execute(
        select(Analysis).where(Analysis.id == job_id, Analysis.user_id == user_id)
    ).scalar_one_or_none()
    if row is None:
        return None
    return {"job_id": str(row.id), "status": row.status,
            **(row.result_json or {}), "errors": (row.result_json or {}).get("errors", [])}


def list_analyses(db: Session, *, user_id: str, limit: int = 20) -> list[dict]:
    rows = db.execute(
        select(Analysis).where(Analysis.user_id == user_id)
        .order_by(Analysis.created_at.desc()).limit(limit)
    ).scalars().all()
    return [{"job_id": str(r.id), "status": r.status, "created_at": r.created_at.isoformat() if r.created_at else None,
             "ats_score": r.ats_score, "company": r.company, "role": r.role} for r in rows]


def delete_analysis(db: Session, *, user_id: str, job_id: str) -> bool:
    """Delete rows (CASCADE). Caller MUST also delete Storage files
    (resumes/{user_id}/*, generated/{user_id}*) — CASCADE cannot do that."""
    row = db.execute(
        select(Analysis).where(Analysis.id == job_id, Analysis.user_id == user_id)
    ).scalar_one_or_none()
    if row is None:
        return False
    db.delete(row)
    db.commit()
    return True
