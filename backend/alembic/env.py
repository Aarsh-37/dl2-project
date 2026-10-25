"""Alembic environment. URL from DATABASE_URL_DIRECT (fallback POOLER).

Revision files must stay import-light (stdlib + sqlalchemy + pgvector only)
so `alembic upgrade head --sql` works anywhere for review (database.md §1).
"""
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:  # `alembic` CLI doesn't load .env on its own
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
except ImportError:
    pass

from app.models import Base  # noqa: E402  (models package must import core tables)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _url() -> str:
    url = os.getenv("DATABASE_URL_DIRECT") or os.getenv("DATABASE_URL_POOLER")
    if not url:
        raise RuntimeError("Set DATABASE_URL_DIRECT (or POOLER) — see .env.example.")
    return url


def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # NOTE: don't use config.set_main_option("sqlalchemy.url", ...) — the
    # ConfigParser interpolation chokes on URL-encoded passwords (%40 etc).
    from sqlalchemy import create_engine

    connectable = create_engine(_url(), poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
