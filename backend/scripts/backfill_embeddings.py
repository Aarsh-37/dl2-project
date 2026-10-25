"""Backfill pgvector embeddings for KB + document chunks (idempotent).

Embeds every row whose embedding IS NULL with ST all-MiniLM-L6-v2 (384-d,
matches the vector(384) columns). First run downloads the ~90MB model once,
then caches it. Safe to re-run — only NULL rows are touched.

    python scripts/backfill_embeddings.py [--limit 500]
"""
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

LIMIT = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else 500
BATCH = 20  # small batches: pooler-safe commits + resumable on drops

# table -> (id column, text expression). COALESCE keeps one non-null text.
TARGETS = {
    "learning_resources": ("id", "title"),
    "question_bank": ("id", "COALESCE(skill || ' ', '') || q"),
    "document_chunks": ("id", "text"),
    "kb_chunks": ("id", "text"),
}


def _vec_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{v:.6f}" for v in vec) + "]"


def main() -> int:
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        print("FAIL: pip install sentence-transformers (see root requirements.txt)")
        return 1
    print("loading ST model (downloads ~90MB on first run)...")
    model = SentenceTransformer("all-MiniLM-L6-v2")
    assert model.get_sentence_embedding_dimension() == 384

    db = get_session()
    try:
        total = 0
        for table, (id_col, text_expr) in TARGETS.items():
            done_table = 0
            attempts = 0
            while done_table < LIMIT and attempts < 4:
                try:
                    rows = db.execute(
                        text(f"SELECT {id_col} AS id, {text_expr} AS t FROM {table} "
                             f"WHERE embedding IS NULL LIMIT :limit"),
                        {"limit": min(BATCH, LIMIT - done_table)},
                    ).all()
                except Exception as exc:
                    attempts += 1
                    db.rollback()
                    db.close()
                    db = get_session()  # pooler dropped us — reconnect, NULL-filter resumes
                    print(f"{table}: reconnect ({attempts}/4): {str(exc)[:100]}")
                    continue
                if not rows:
                    break
                texts = [(r[0], r[1] or "") for r in rows]
                vecs = model.encode([t for _, t in texts], convert_to_numpy=True,
                                    show_progress_bar=False)
                try:
                    for (rid, _), vec in zip(texts, vecs):
                        db.execute(
                            text(f"UPDATE {table} SET embedding = CAST(:emb AS vector) "
                                 f"WHERE {id_col} = :rid"),
                            {"emb": _vec_literal([float(v) for v in vec]), "rid": rid},
                        )
                    db.commit()
                except Exception as exc:
                    attempts += 1
                    db.rollback()
                    db.close()
                    db = get_session()
                    print(f"{table}: reconnect ({attempts}/4): {str(exc)[:100]}")
                    continue
                done_table += len(rows)
                total += len(rows)
                print(f"{table}: embedded {done_table} rows")
            if attempts >= 4:
                print(f"FAIL {table}: pooler kept dropping — re-run later (resumes where it left off)")
                return 1
        print(f"BACKFILL: {total} rows total")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
