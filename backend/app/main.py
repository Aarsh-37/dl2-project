"""CareerPilot AI — FastAPI entry (Phase 4.1: plain-function pipeline).

Routers are thin: validate → run → return. Logic lives in core/pipeline.py +
services/ + tools/. Run:  uvicorn app.main:app --reload --port 8010  (from backend/)
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import analyze, interviews, results, resumes


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Warm heavy singletons at boot (once) so requests stay under budget.

    ST embeddings (~90s first load) + torch import would otherwise land
    mid-request on the first analysis. Failures here never block startup.
    """
    try:
        from app.tools.embeddings import embed

        embed("warmup")
    except Exception:
        pass
    try:
        from app.services.skill_vae import _load

        _load()
    except Exception:
        pass
    try:  # pay DNS + first handshake once, warming the shared pool
        import concurrent.futures as _fut

        from app.db.session import pooler_engine
        from sqlalchemy import text as _text

        def _ping():
            with pooler_engine().connect() as conn:
                conn.execute(_text("SELECT 1"))

        _fut.ThreadPoolExecutor(max_workers=1).submit(_ping).result(timeout=30)
    except Exception:
        pass
    yield


app = FastAPI(title="CareerPilot AI", lifespan=lifespan)


def _origins() -> list[str]:
    raw = os.getenv("FRONTEND_URL", "http://localhost:3000")
    extra = [o.strip() for o in raw.split(",") if o.strip()]
    defaults = ["http://localhost:3000", "http://127.0.0.1:3000",
                "http://localhost:3001", "http://127.0.0.1:3001"]
    return list(dict.fromkeys(extra + defaults))


app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analyze.router)
app.include_router(results.router)
app.include_router(interviews.router)
app.include_router(resumes.router)


@app.get("/health")
async def health():
    return {"ok": True}


@app.get("/health/db")
async def health_db():
    from sqlalchemy import text
    try:
        from app.db.session import pooler_engine
        engine = pooler_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"ok": True, "database": "connected"}
    except Exception as exc:
        return {"ok": False, "database": "error", "detail": str(exc)}


@app.get("/ready")
async def ready():
    from app.core.config import SKILL_TAXONOMY_CSV
    from sqlalchemy import text

    db_ok = False
    try:
        from app.db.session import pooler_engine
        engine = pooler_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    return {
        "ok": True,
        "taxonomy": SKILL_TAXONOMY_CSV.exists(),
        "database": db_ok,
    }
