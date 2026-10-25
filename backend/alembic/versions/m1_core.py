"""Alembic m1: core + document_chunks + skills (+ seed, RLS).

Pure DDL + seed; mirrors app/models/core.py. Review offline first:
  alembic upgrade head --sql
Seed is idempotent (ON CONFLICT DO NOTHING) so re-runs are safe.
"""
import csv
from pathlib import Path

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB

revision = "m1_core"
down_revision = None
branch_labels = None
depends_on = None

TAXONOMY_CSV = Path(__file__).resolve().parents[3] / "data" / "skill_taxonomy.csv"

USER_TABLES = (
    "profiles", "resumes", "job_descriptions", "analyses",
)  # resume_versions/document_chunks/skills/skill_gaps have no user_id — owned via parents / shared KB


def _uuid(name="id", pk=True):
    return sa.Column(
        name, sa.Uuid(as_uuid=True), primary_key=pk,
        server_default=sa.text("gen_random_uuid()"),
    )


def _user_fk():
    return sa.Column(
        "user_id", sa.Uuid(as_uuid=True),
        sa.ForeignKey("auth.users.id", ondelete="CASCADE"), nullable=False,
    )


def _ensure_auth_shim() -> None:
    """Local scratch DBs have no auth schema; real Supabase always has
    auth.users (but won't let us touch the auth schema — skip it there)."""
    bind = op.get_bind()
    exists = bind.execute(sa.text(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema='auth' AND table_name='users'")).first()
    if exists:
        return
    try:
        with bind.begin_nested():
            bind.execute(sa.text("CREATE SCHEMA IF NOT EXISTS auth"))
            bind.execute(sa.text("CREATE TABLE IF NOT EXISTS auth.users (id uuid PRIMARY KEY)"))
    except Exception:
        pass  # managed Supabase: FK below still resolves to the real auth.users


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
    _ensure_auth_shim()

    op.create_table(
        "profiles",
        _uuid(), _user_fk(),
        sa.Column("full_name", sa.Text),
        sa.Column("level", sa.String(20)),
        sa.Column("target_role", sa.Text),
        sa.Column("location", sa.Text),
        sa.Column("hours_per_day", sa.Integer, server_default="3"),
        sa.Column("prefs", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.CheckConstraint("level IN ('fresher','experienced')", name="profiles_level_check"),
        sa.UniqueConstraint("user_id", name="uq_profiles_user"),
    )
    op.create_table(
        "resumes",
        _uuid(), _user_fk(),
        sa.Column("file_url", sa.Text, nullable=False),
        sa.Column("raw_text", sa.Text),
        sa.Column("sha256", sa.CHAR(64)),
        sa.Column("parsed_json", JSONB),
        sa.Column("embedding", Vector(384)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_table(
        "resume_versions",
        _uuid(),
        sa.Column("resume_id", sa.Uuid(as_uuid=True),
                  sa.ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("file_url", sa.Text),
        sa.Column("md_text", sa.Text),
        sa.UniqueConstraint("resume_id", "version", name="uq_resume_versions"),
    )
    op.create_table(
        "document_chunks",
        _uuid(),
        sa.Column("owner_type", sa.String(10), nullable=False),
        sa.Column("owner_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("section", sa.Text),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("embedding", Vector(384)),
        sa.CheckConstraint("owner_type IN ('resume','jd','job')", name="chunks_owner_check"),
        sa.UniqueConstraint("owner_type", "owner_id", "chunk_index", name="uq_chunks"),
    )
    op.create_table(
        "job_descriptions",
        _uuid(), _user_fk(),
        sa.Column("raw_text", sa.Text, nullable=False),
        sa.Column("parsed_json", JSONB),
        sa.Column("company", sa.Text),
        sa.Column("role", sa.Text),
        sa.Column("embedding", Vector(384)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_table(
        "analyses",
        _uuid(), _user_fk(),
        sa.Column("resume_id", sa.Uuid(as_uuid=True),
                  sa.ForeignKey("resumes.id", ondelete="SET NULL")),
        sa.Column("jd_id", sa.Uuid(as_uuid=True),
                  sa.ForeignKey("job_descriptions.id", ondelete="SET NULL")),
        sa.Column("company", sa.Text),
        sa.Column("role", sa.Text),
        sa.Column("level", sa.String(20)),
        sa.Column("hours_per_day", sa.Integer),
        sa.Column("status", sa.String(10), server_default="queued"),
        sa.Column("result_json", JSONB),
        sa.Column("ats_score", sa.Integer),
        sa.Column("error_log", JSONB, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.CheckConstraint(
            "status IN ('queued','running','partial','done','failed')",
            name="analyses_status_check"),
    )
    op.create_table(
        "skills",
        _uuid(),
        sa.Column("name", sa.Text, unique=True, nullable=False),
        sa.Column("alias_of", sa.Text),
        sa.Column("category", sa.Text),
    )
    op.create_table(
        "resume_skills",
        sa.Column("resume_id", sa.Uuid(as_uuid=True),
                  sa.ForeignKey("resumes.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("skill_id", sa.Uuid(as_uuid=True),
                  sa.ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("proficiency", sa.Text),
    )
    op.create_table(
        "jd_skills",
        sa.Column("jd_id", sa.Uuid(as_uuid=True),
                  sa.ForeignKey("job_descriptions.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("skill_id", sa.Uuid(as_uuid=True),
                  sa.ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("requirement", sa.String(10)),
        sa.CheckConstraint("requirement IN ('required','preferred')", name="jd_skills_req_check"),
    )
    op.create_table(
        "skill_gaps",
        _uuid(),
        sa.Column("analysis_id", sa.Uuid(as_uuid=True),
                  sa.ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("skill_id", sa.Uuid(as_uuid=True),
                  sa.ForeignKey("skills.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("reason", sa.Text),
        sa.Column("weeks_to_learn", sa.Integer),
        sa.CheckConstraint(
            "status IN ('strong','partial','missing','critical_missing')",
            name="skill_gaps_status_check"),
    )

    op.create_index("ix_analyses_user_created", "analyses", ["user_id", "created_at"])
    op.create_index("ix_skill_gaps_analysis", "skill_gaps", ["analysis_id"])
    op.create_index("ix_chunks_owner", "document_chunks", ["owner_type", "owner_id"])

    # RLS as defense-in-depth (app still filters by user_id — database.md §5).
    for table in USER_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY own_rows ON {table} FOR ALL "
            f"USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id)"
        )

    _seed_skills()


def _seed_skills() -> None:
    bind = op.get_bind()
    with open(TAXONOMY_CSV, newline="", encoding="utf-8") as fh:
        rows = [
            {"name": r["name"], "alias_of": r["alias_of"] or None, "category": r["category"] or None}
            for r in csv.DictReader(fh) if (r.get("name") or "").strip()
        ]
    stmt = sa.text(
        "INSERT INTO skills (name, alias_of, category) "
        "VALUES (:name, :alias_of, :category) ON CONFLICT (name) DO NOTHING"
    )
    for i in range(0, len(rows), 100):
        bind.execute(stmt, rows[i:i + 100])


def downgrade() -> None:
    for table in USER_TABLES:
        op.execute(f"DROP POLICY IF EXISTS own_rows ON {table}")
    for table in (
        "skill_gaps", "jd_skills", "resume_skills", "skills", "analyses",
        "job_descriptions", "document_chunks", "resume_versions", "resumes", "profiles",
    ):
        op.drop_table(table)
