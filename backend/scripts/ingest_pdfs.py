"""RAG ingest: PDF -> pages (text/OCR) -> chunks -> ST embeddings -> kb_chunks.

Sources live in data/kb/*.pdf. Idempotent (UNIQUE source+chunk_index):
re-running only fills gaps. Flags:

    python scripts/ingest_pdfs.py [--source skills|hr] [--dry-run] [--limit-pages N]

--dry-run parses + chunks without touching the DB or the ST model.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
except ImportError:
    pass

from app.core.config import SKILL_TAXONOMY_CSV
from app.tools import pdf_ingest, skill_extract

KB_DIR = Path(__file__).resolve().parents[2] / "data" / "kb"
SOURCES = {
    "skills": {"file": "Skills_Interview_Questions_and_Answers.pdf",
               "category": "technical", "min_q": 2},
    "hr": {"file": "HR Interview Questions.pdf",
           "category": "hr", "min_chars": 100},
}
CHUNK_SIZE, CHUNK_OVERLAP, BATCH = 800, 100, 10


def _hardened_engine():
    """Own engine (not the shared session): short connects, 20s statement
    cap so pooler stalls fail fast instead of hanging forever."""
    import os

    from sqlalchemy import create_engine
    from sqlalchemy.pool import NullPool

    from app.db.session import _sync_url

    url = _sync_url(os.getenv("DATABASE_URL_POOLER", ""))
    sep = "&" if "?" in url else "?"
    url = f"{url}{sep}options=-c%20statement_timeout%3D20s"
    # prepare_threshold=None forces the simple query protocol: Supavisor
    # transaction pooling breaks server-side prepared statements.
    return create_engine(url, poolclass=NullPool,
                         connect_args={"connect_timeout": 15,
                                       "prepare_threshold": None})


def build_rows(source: str, limit_pages: int = 0, start_page: int = 1) -> list[dict]:
    """Parse + chunk a PDF into kb_chunks rows (no DB, no embeddings).

    chunk_index is deterministic (page * 1000 + position), so --start-page
    resumes produce identical indices and ON CONFLICT stays correct.
    """
    cfg = SOURCES[source]
    if source == "skills":
        # Text PDF: extraction is cheap, so scan everything (perfect skill
        # context) and slice the page range afterwards.
        pages = pdf_ingest.extract_pages(KB_DIR / cfg["file"])
    else:
        # OCR PDF: render only the requested range (minutes per page).
        pages = pdf_ingest.extract_pages(KB_DIR / cfg["file"],
                                         start_page=start_page,
                                         limit_pages=limit_pages)
    taxonomy = skill_extract.load_taxonomy(SKILL_TAXONOMY_CSV)
    pages = pdf_ingest.tag_skill_pages(pages, taxonomy)
    if source == "skills":
        pages = [p for p in pages if p["page"] >= start_page]
        if limit_pages:
            pages = pages[:limit_pages]
    rows: list[dict] = []
    for page in pages:
        text = page["text"]
        if source == "skills" and len(re.findall(r"(?m)^Q\d{1,3}\.", text)) < cfg["min_q"]:
            continue  # contents/intro pages carry no Q&A
        if source == "hr" and len(text) < cfg["min_chars"]:
            continue  # dedication/blank pages
        for j, chunk in enumerate(pdf_ingest.chunk_text(text, CHUNK_SIZE, CHUNK_OVERLAP)):
            rows.append({"source": cfg["file"],
                         "skill": page.get("skill") or ("General" if source == "hr" else None),
                         "category": cfg["category"], "page": page["page"],
                         "chunk_index": page["page"] * 1000 + j, "text": chunk})
    return rows


def _vec_literal(vec) -> str:
    return "[" + ",".join(f"{float(v):.6f}" for v in vec) + "]"


def main() -> int:
    args = sys.argv[1:]
    only = args[args.index("--source") + 1] if "--source" in args else None
    dry = "--dry-run" in args
    limit = int(args[args.index("--limit-pages") + 1]) if "--limit-pages" in args else 0
    start = int(args[args.index("--start-page") + 1]) if "--start-page" in args else 1
    sources = [only] if only else list(SOURCES)
    rows: list[dict] = []
    for source in sources:
        built = build_rows(source, limit, start)
        print(f"{source}: {len(built)} chunks", flush=True)
        rows.extend(built)
    if dry or not rows:
        print(f"DRY-RUN: {len(rows)} rows, nothing written")
        return 0

    from sqlalchemy import text

    from app.db.session import get_session

    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        print("FAIL: pip install sentence-transformers")
        return 1
    print("loading ST model...")
    model = SentenceTransformer("all-MiniLM-L6-v2")

    stmt = text(
        "INSERT INTO kb_chunks (source, skill, category, page, chunk_index, text, embedding) "
        "VALUES (:source, :skill, :category, :page, :chunk_index, :text, "
        "CAST(:embedding AS vector)) "
        "ON CONFLICT (source, chunk_index) DO NOTHING")
    done = 0
    for attempt in range(1, 6):
        eng = _hardened_engine()
        try:
            with eng.connect() as conn:
                have = {r[0] for r in conn.execute(
                    text("SELECT chunk_index FROM kb_chunks WHERE source = :src"),
                    {"src": rows[0]["source"]}).all()} if rows else set()
                pending = [r for r in rows if r["chunk_index"] not in have
                           and r.get("embedding") is None]
                texts = [r["text"] for r in pending]
                if texts:
                    print(f"encoding {len(texts)} new chunks...", flush=True)
                    vecs = model.encode(texts, convert_to_numpy=True,
                                        show_progress_bar=False)
                    for r, v in zip(pending, vecs):
                        r["embedding"] = _vec_literal(v)
                todo = [r for r in rows if r["chunk_index"] not in have]
                for i in range(0, len(todo), BATCH):
                    conn.execute(stmt, [{**r} for r in todo[i:i + BATCH]])
                    conn.commit()
                    done = max(done, min(i + BATCH, len(todo)))
                    print(f"  wrote {done}/{len(todo)}", flush=True)
                print(f"INGEST OK: {len(rows)} rows ({len(todo)} new)")
                return 0
        except Exception as exc:
            print(f"reconnect ({attempt}/5): {str(exc)[:120]}", flush=True)
        finally:
            eng.dispose()
    print("FAIL: pooler kept dropping")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
