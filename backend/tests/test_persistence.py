"""Persistence integration tests. Require a scratch Postgres + pgvector:

    TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:54322/scratch
    pytest tests/test_persistence.py -q

Skipped otherwise. Never run against the real Supabase project.
"""
import os
import uuid

import pytest

TEST_URL = os.getenv("TEST_DATABASE_URL")
needs_db = pytest.mark.skipif(not TEST_URL, reason="TEST_DATABASE_URL not set")


@needs_db
def test_save_load_round_trip_and_user_isolation():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.models import Base
    from app.services import analysis_service as svc

    engine = create_engine(TEST_URL)
    Base.metadata.drop_all(engine)
    from sqlalchemy import text
    with engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS auth"))
    Base.metadata.create_all(engine)
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            for name in ("Python", "SQL", "Git", "Docker"):
                conn.execute(
                    text("INSERT INTO skills (name) VALUES (:n) ON CONFLICT DO NOTHING"),
                    {"n": name},
                )
        user_a, user_b = str(uuid.uuid4()), str(uuid.uuid4())
        with engine.begin() as conn:
            for uid in (user_a, user_b):
                conn.execute(
                    text("INSERT INTO auth.users (id) VALUES (:u) ON CONFLICT DO NOTHING"),
                    {"u": uid},
                )
        with Session(engine) as db:
            row = svc.save_analysis(
                db, user_id=user_a, resume_file_url="resumes/x/r.pdf",
                resume_text="Python dev with SQL and Git. " * 30,
                jd_text="Need Python, SQL. Prefer Docker.",
                candidate_skills=["Python", "SQL", "Git"],
                required=["Python", "SQL"], preferred=["Docker"],
                ats={"score": 70, "breakdown": {}, "verdict": "Moderate",
                     "strengths": [], "gaps": [], "improvements": [],
                     "quick_wins": [], "rationale": "t"},
                gaps={"strong": ["Python", "SQL"], "partial": [],
                      "missing": [{"skill": "Docker", "criticality": "Medium",
                                   "reason": "r", "weeks_to_learn": 3}],
                      "critical_missing": []},
            )
            job_id = str(row.id)
            loaded = svc.load_analysis(db, user_id=user_a, job_id=job_id)
            assert loaded["status"] == "done"
            assert loaded["ats_result"]["score"] == 70
            # Cross-user access returns None (app-level enforcement).
            assert svc.load_analysis(db, user_id=user_b, job_id=job_id) is None
            assert svc.list_analyses(db, user_id=user_a)[0]["job_id"] == job_id
            assert svc.list_analyses(db, user_id=user_b) == []
            assert svc.delete_analysis(db, user_id=user_b, job_id=job_id) is False
            assert svc.delete_analysis(db, user_id=user_a, job_id=job_id) is True
            assert svc.load_analysis(db, user_id=user_a, job_id=job_id) is None
    finally:
        Base.metadata.drop_all(engine)
