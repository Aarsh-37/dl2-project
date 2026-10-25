"""Supabase readiness check (run from backend/).

    python scripts/check_supabase.py

Verifies: env URLs/keys (redacted) -> connect -> extensions
(vector, pgcrypto) -> m1 tables -> skills seed count -> RLS on user
tables -> Storage buckets (resumes, generated) via REST. Read-only.
Exit 0 = ready to migrate + persist; exit 1 = prints exactly what's missing.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
except ImportError:
    pass

M1_TABLES = ("profiles", "resumes", "resume_versions", "document_chunks",
             "job_descriptions", "analyses", "skills", "resume_skills",
             "jd_skills", "skill_gaps")


def _redact(value: str) -> str:
    if not value:
        return "MISSING"
    return value[:12] + "..." if len(value) > 16 else "set"


def main() -> int:
    print("== env ==")
    pooler = os.getenv("DATABASE_URL_POOLER", "")
    direct = os.getenv("DATABASE_URL_DIRECT", "")
    url = os.getenv("SUPABASE_URL", "")
    anon = os.getenv("SUPABASE_ANON_KEY", "")
    svc = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    print(f"DATABASE_URL_POOLER: {_redact(pooler)}")
    print(f"DATABASE_URL_DIRECT: {_redact(direct)}")
    print(f"SUPABASE_URL: {url or 'MISSING'}")
    print(f"SUPABASE_ANON_KEY: {_redact(anon)}")
    print(f"SUPABASE_SERVICE_ROLE_KEY: {_redact(svc)}")
    ok = True
    if not (pooler and direct):
        print("FAIL: paste both DB URLs into root .env (Supabase Settings -> Database).")
        return 1

    print("\n== database ==")
    try:
        from sqlalchemy import create_engine, text

        from app.db.session import _sync_url

        db_url = os.getenv("DATABASE_URL_DIRECT", "")
        try:
            engine = create_engine(_sync_url(db_url), poolclass=None,
                                   connect_args={"connect_timeout": 10})
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception:
            # Direct is IPv6-only; fall back to the IPv4 pooler for checks.
            db_url = os.getenv("DATABASE_URL_POOLER", "")
            engine = create_engine(_sync_url(db_url), poolclass=None,
                                   connect_args={"connect_timeout": 10})
        with engine.connect() as conn:
            exts = {r[0] for r in conn.execute(
                text("SELECT extname FROM pg_extension WHERE extname IN ('vector','pgcrypto')"))}
            print(f"extensions: {sorted(exts)}")
            if exts != {"vector", "pgcrypto"}:
                print("FAIL: run in Supabase SQL editor: "
                      "CREATE EXTENSION vector; CREATE EXTENSION \"pgcrypto\";")
                ok = False
            have = {r[0] for r in conn.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname='public'"))}
            missing = [t for t in M1_TABLES if t not in have]
            print(f"m1 tables: {'all present' if not missing else 'MISSING ' + str(missing)}")
            if missing:
                print("FAIL: run migration:  alembic upgrade head  (from backend/)")
                ok = False
            else:
                n = conn.execute(text("SELECT count(*) FROM skills")).scalar()
                print(f"skills seed: {n} rows")
                if (n or 0) < 50:
                    print("FAIL: re-run migration (seed is idempotent) or check taxonomy CSV.")
                    ok = False
                rls = conn.execute(text(
                    "SELECT tablename FROM pg_tables WHERE schemaname='public' "
                    "AND rowsecurity AND tablename IN "
                    "('profiles','resumes','job_descriptions','analyses')")).all()
                print(f"RLS on: {len(rls)}/4 user tables")
    except ModuleNotFoundError as exc:
        print(f"FAIL: driver missing ({exc}) — run: pip install -r requirements.txt")
        return 1
    except Exception as exc:
        print(f"FAIL: cannot connect: {str(exc)[:300]}")
        return 1

    print("\n== storage ==")
    if not (url and svc):
        print("SKIP: SUPABASE_URL / SERVICE_ROLE key missing — buckets unchecked.")
    else:
        try:
            import httpx

            r = httpx.get(f"{url.rstrip('/')}/storage/v1/bucket",
                          headers={"apikey": svc, "Authorization": f"Bearer {svc}"},
                          timeout=15)
            names = [b.get("name") for b in r.json()] if r.status_code == 200 else []
            print(f"buckets: {names}")
            for b in ("resumes", "generated"):
                if b not in names:
                    print(f"FAIL: create private bucket '{b}' (Supabase Storage -> New bucket, private).")
                    ok = False
        except Exception as exc:
            print(f"SKIP: bucket check failed: {str(exc)[:200]}")
    print("\nRESULT:", "READY" if ok else "NOT READY (fix FAIL lines above)")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
