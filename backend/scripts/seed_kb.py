"""Seed KB tables from app/services/kb_service.py + your own data/kb/*.csv
(idempotent — safe to re-run).

    python scripts/seed_kb.py

Your files (exact names, headers must match data/kb/*.example.csv):
  data/kb/learning_resources.csv → skill,title,url,type
  data/kb/questions.csv          → skill,category,difficulty,q,ideal_answer,key_points
key_points are separated with | e.g. "STAR|Trade-offs|Outcome".
"""
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
except ImportError:
    pass

from sqlalchemy import text

from app.db.session import get_session
from app.services import kb_service as kb
from app.services.kb_ingest import load_user_csvs

KB_DIR = Path(__file__).resolve().parents[2] / "data" / "kb"


def _insert_batches(db, stmt, rows: list[dict], batch: int = 50) -> int:
    """Insert in small pooler-safe batches. ON CONFLICT DO NOTHING makes
    resume-after-reconnect safe (reconnect from caller on failure)."""
    inserted = 0
    for i in range(0, len(rows), batch):
        inserted += db.execute(stmt, rows[i:i + batch]).rowcount
        db.commit()
    return inserted


def main() -> int:
    last_exc: Exception | None = None
    for attempt in range(1, 4):
        db = get_session()
        try:
            return _seed(db)
        except Exception as exc:  # pooler drop — ON CONFLICT makes retry safe
            last_exc = exc
            print(f"reconnect ({attempt}/3): {str(exc)[:120]}")
            try:
                db.rollback()
            except Exception:
                pass
        finally:
            try:
                db.close()
            except Exception:
                pass
    print(f"FAIL: {last_exc}")
    return 1


def _seed(db) -> int:
    try:
        res_ins = _insert_batches(db,
            text("INSERT INTO learning_resources (skill, title, url, type) "
                 "VALUES (:skill, :title, :url, :type) "
                 "ON CONFLICT (skill, url) DO NOTHING"),
            kb.RESOURCES)
        q_rows = [{"skill": q["skill"], "category": q["category"],
                   "difficulty": q["difficulty"], "q": q["q"],
                   "ideal_answer": q["ideal_answer"],
                   "key_points": json.dumps(q["key_points"])} for q in kb.QUESTIONS]
        q_ins = _insert_batches(db,
            text("INSERT INTO question_bank (skill, category, difficulty, q, ideal_answer, key_points) "
                 "VALUES (:skill, :category, :difficulty, :q, :ideal_answer, "
                 "CAST(:key_points AS jsonb)) "
                 "ON CONFLICT (skill, category, q) DO NOTHING"),
            q_rows)
        user_res, user_q = load_user_csvs(KB_DIR)
        if user_res:
            u_res = _insert_batches(db,
                text("INSERT INTO learning_resources (skill, title, url, type) "
                     "VALUES (:skill, :title, :url, :type) "
                     "ON CONFLICT (skill, url) DO NOTHING"),
                user_res)
            print(f"user csv: {u_res} new resources from data/kb/learning_resources.csv")
        if user_q:
            uq_rows = [{**q, "key_points": json.dumps(q["key_points"])} for q in user_q]
            u_q = _insert_batches(db,
                text("INSERT INTO question_bank (skill, category, difficulty, q, ideal_answer, key_points) "
                     "VALUES (:skill, :category, :difficulty, :q, :ideal_answer, "
                     "CAST(:key_points AS jsonb)) "
                     "ON CONFLICT (skill, category, q) DO NOTHING"),
                uq_rows)
            print(f"user csv: {u_q} new questions from data/kb/questions.csv")
            q_ins += u_q
        n_res = db.execute(text("SELECT count(*) FROM learning_resources")).scalar()
        n_q = db.execute(text("SELECT count(*) FROM question_bank")).scalar()
        print(f"inserted: {res_ins} resources, {q_ins} questions")
        print(f"totals: {n_res} learning_resources, {n_q} question_bank")
        ok = (n_res or 0) >= 50 and (n_q or 0) >= 50
        print("SEED:", "OK" if ok else "SHORT (check curated counts)")
        return 0 if ok else 1
    except Exception:
        db.rollback()
        raise


if __name__ == "__main__":
    raise SystemExit(main())
