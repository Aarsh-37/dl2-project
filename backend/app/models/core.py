"""Alembic m1 models: core + document_chunks + skills. No users table.

Conventions (database.md §3): id uuid PK, created_at timestamptz server
default, every user row has user_id FK auth.users ON DELETE CASCADE,
embedding vector(384) nullable until backfilled. analyses.id IS job_id.
"""
import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CHAR,
    Boolean,
    CheckConstraint,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _user_fk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False,
    )


def _created_at() -> Mapped:
    from sqlalchemy import DateTime

    return mapped_column(DateTime(timezone=True), server_default=func.now())


class AuthUser(Base):
    """Metadata-only stub for Supabase-managed auth.users (never migrated).

    Registers the table in metadata so flush-time dependency sorting can
    resolve user_id FKs. Alembic m1 is hand-written and ignores this model.
    """
    __tablename__ = "users"
    __table_args__ = {"schema": "auth"}
    id: Mapped[uuid.UUID] = _uuid_pk()


class Profile(Base):
    __tablename__ = "profiles"
    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False, unique=True,
    )
    full_name: Mapped[str | None] = mapped_column(Text)
    level: Mapped[str | None] = mapped_column(String(20))
    target_role: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(Text)
    hours_per_day: Mapped[int] = mapped_column(Integer, default=3)
    prefs: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at = _created_at()
    __table_args__ = (CheckConstraint("level IN ('fresher','experienced')", name="profiles_level_check"),)


class Resume(Base):
    __tablename__ = "resumes"
    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = _user_fk()
    file_url: Mapped[str] = mapped_column(Text, nullable=False)
    raw_text: Mapped[str | None] = mapped_column(Text)
    sha256: Mapped[str | None] = mapped_column(CHAR(64))
    parsed_json: Mapped[dict | None] = mapped_column(JSONB)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(384))
    created_at = _created_at()


class ResumeVersion(Base):
    __tablename__ = "resume_versions"
    id: Mapped[uuid.UUID] = _uuid_pk()
    resume_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    file_url: Mapped[str | None] = mapped_column(Text)
    md_text: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (UniqueConstraint("resume_id", "version", name="uq_resume_versions"),)


class DocumentChunk(Base):
    """Per-section/per-chunk vectors. Section-weighted ATS is v2; v1 uses
    doc-level embeddings. No user_id (polymorphic owner); service-role +
    app filters only, no RLS — see database.md §5."""
    __tablename__ = "document_chunks"
    id: Mapped[uuid.UUID] = _uuid_pk()
    owner_type: Mapped[str] = mapped_column(String(10), nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    section: Mapped[str | None] = mapped_column(Text)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(384))
    __table_args__ = (
        CheckConstraint("owner_type IN ('resume','jd','job')", name="chunks_owner_check"),
        UniqueConstraint("owner_type", "owner_id", "chunk_index", name="uq_chunks"),
    )


class JobDescription(Base):
    __tablename__ = "job_descriptions"
    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = _user_fk()
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    parsed_json: Mapped[dict | None] = mapped_column(JSONB)
    company: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str | None] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(384))
    created_at = _created_at()


class Analysis(Base):
    """analyses.id IS job_id (contracts.md §1). result_json follows §5.1."""
    __tablename__ = "analyses"
    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = _user_fk()
    resume_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resumes.id", ondelete="SET NULL"))
    jd_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_descriptions.id", ondelete="SET NULL"))
    company: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str | None] = mapped_column(Text)
    level: Mapped[str | None] = mapped_column(String(20))
    hours_per_day: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(10), server_default="queued")
    result_json: Mapped[dict | None] = mapped_column(JSONB)
    ats_score: Mapped[int | None] = mapped_column(Integer)
    error_log: Mapped[list] = mapped_column(JSONB, default=list)
    created_at = _created_at()
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued','running','partial','done','failed')",
            name="analyses_status_check",
        ),
    )


class Skill(Base):
    """Shared KB (seeded from data/skill_taxonomy.csv). No user_id; SELECT for
    authenticated, writes via service role only."""
    __tablename__ = "skills"
    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    alias_of: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(Text)


class ResumeSkill(Base):
    __tablename__ = "resume_skills"
    resume_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resumes.id", ondelete="CASCADE"), primary_key=True)
    skill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True)
    proficiency: Mapped[str | None] = mapped_column(Text)


class JdSkill(Base):
    __tablename__ = "jd_skills"
    jd_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_descriptions.id", ondelete="CASCADE"), primary_key=True)
    skill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True)
    requirement: Mapped[str | None] = mapped_column(String(10))
    __table_args__ = (
        CheckConstraint("requirement IN ('required','preferred')", name="jd_skills_req_check"),
    )


class SkillGap(Base):
    __tablename__ = "skill_gaps"
    id: Mapped[uuid.UUID] = _uuid_pk()
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False)
    skill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    weeks_to_learn: Mapped[int | None] = mapped_column(Integer)
    __table_args__ = (
        CheckConstraint(
            "status IN ('strong','partial','missing','critical_missing')",
            name="skill_gaps_status_check",
        ),
    )
