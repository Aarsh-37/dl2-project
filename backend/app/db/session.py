"""DB engines. Two URLs (database.md §6, contracts frozen):

- POOLER (DATABASE_URL_POOLER): normal ORM traffic.
- DIRECT (DATABASE_URL_DIRECT, session/direct mode): LangGraph checkpointer
  (Phase 4) — never the pooler for langgraph-checkpoint-postgres.

Sync SQLAlchemy (v1); async migration is a later optimization, not a blocker.
Service-role connection bypasses RLS, so every query MUST filter by user_id
(database.md §5) — see services/analysis_service.py.

Timeout policy: Supavisor pooler stalls are fail-fast (10s connect,
15s statement) so a flaky network degrades to fallbacks instead of
hanging API requests. KB reads are best-effort and catch these.
"""
import os
from pathlib import Path

from sqlalchemy import create_engine

try:  # auto-load project-root .env so URLs work without manual export
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[3] / ".env", override=False)
except ImportError:
    pass

# Fail fast on the flaky pooler path: connect + per-statement ceilings.
_CONNECT_ARGS = {"connect_timeout": 10,
                 "options": "-c statement_timeout=15000"}

import threading as _threading

_ENGINE_LOCK = _threading.Lock()
_POOLER_ENGINE = None


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is not set (see .env.example).")
    return value


def _sync_url(url: str) -> str:
    """Sync engine can't use the asyncpg driver — coerce to psycopg."""
    if url.startswith("postgresql+asyncpg://"):
        return "postgresql+psycopg://" + url[len("postgresql+asyncpg://"):]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def pooler_engine():
    """Process-wide singleton: one DNS lookup, one warm pool.

    Per-call engines were opening a fresh TCP+TLS+auth handshake for EVERY
    query (and leaking pools) — minutes of overhead per analysis on a
    flaky network, plus connection exhaustion on Supabase free tier.
    """
    global _POOLER_ENGINE
    if _POOLER_ENGINE is None:
        with _ENGINE_LOCK:
            if _POOLER_ENGINE is None:
                _POOLER_ENGINE = create_engine(
                    _sync_url(_require("DATABASE_URL_POOLER")),
                    pool_size=5, max_overflow=5, connect_args=_CONNECT_ARGS)
    return _POOLER_ENGINE


def direct_engine():
    """Direct/session-mode engine. Reserved for the LangGraph checkpointer."""
    return create_engine(_sync_url(_require("DATABASE_URL_DIRECT")),
                         pool_size=2, max_overflow=0, connect_args=_CONNECT_ARGS)


SessionLocal = None  # kept for API-compat; prefer get_session() (env-checked lazily)


def get_session():
    """Session on the shared pooler engine (works even if env was set after import)."""
    from sqlalchemy.orm import Session

    return Session(pooler_engine())
