"""Alembic m3: kb_chunks vector store (embedding + text + metadata).

Import-light (stdlib + sqlalchemy + pgvector only).
"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = "m3_kb_chunks"
down_revision = "m2_kb"
branch_labels = None
depends_on = None


def _uuid(name="id", pk=True):
    return sa.Column(
        name, sa.Uuid(as_uuid=True), primary_key=pk,
        server_default=sa.text("gen_random_uuid()"),
    )


def upgrade() -> None:
    op.create_table(
        "kb_chunks",
        _uuid(),
        sa.Column("source", sa.Text, nullable=False),
        sa.Column("skill", sa.Text),
        sa.Column("category", sa.Text),
        sa.Column("page", sa.Integer),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("embedding", Vector(384)),
        sa.UniqueConstraint("source", "chunk_index", name="uq_kb_chunks"),
    )
    op.create_index("ix_kb_chunks_skill", "kb_chunks", ["skill"])
    op.create_index("ix_kb_chunks_source", "kb_chunks", ["source"])


def downgrade() -> None:
    op.drop_table("kb_chunks")
