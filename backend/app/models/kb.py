"""m2 KB models: shared learning_resources + question_bank (no user_id).

Writes via service role only; SELECT for authenticated (grants managed
explicitly — auto-expose stays off per project decision).
"""
import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class LearningResource(Base):
    __tablename__ = "learning_resources"
    id: Mapped[uuid.UUID] = _uuid_pk()
    skill: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str | None] = mapped_column(String(10))  # docs|video|course|practice
    free: Mapped[bool] = mapped_column(Boolean, default=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(384))
    __table_args__ = (UniqueConstraint("skill", "url", name="uq_learning_skill_url"),)


class QuestionBank(Base):
    __tablename__ = "question_bank"
    id: Mapped[uuid.UUID] = _uuid_pk()
    skill: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(Text)  # technical|hr
    difficulty: Mapped[str | None] = mapped_column(Text)
    q: Mapped[str] = mapped_column(Text, nullable=False)
    ideal_answer: Mapped[str | None] = mapped_column(Text)
    key_points: Mapped[list | None] = mapped_column(JSONB)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(384))
    __table_args__ = (UniqueConstraint("skill", "category", "q", name="uq_qbank"),)


class KbChunk(Base):
    """Raw chunk store for the RAG ingest pipeline:

    PDF -> page text (/OCR) -> overlapping chunks -> ST embedding ->
    one row per chunk carrying its embedding + original text + metadata.
    Retrieval: pgvector cosine over embedding, filtered by source/skill.
    """
    __tablename__ = "kb_chunks"
    id: Mapped[uuid.UUID] = _uuid_pk()
    source: Mapped[str] = mapped_column(Text, nullable=False)  # e.g. skills_interview_qa.pdf
    skill: Mapped[str | None] = mapped_column(Text)  # taxonomy canonical when known
    category: Mapped[str | None] = mapped_column(Text)  # technical|hr
    page: Mapped[int | None] = mapped_column(Integer)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(384))
    __table_args__ = (UniqueConstraint("source", "chunk_index", name="uq_kb_chunks"),)


def _created_at() -> Mapped:  # reserved for per-run tables (m2+); KB rows are seed data
    from sqlalchemy import DateTime

    return mapped_column(DateTime(timezone=True), server_default=func.now())
