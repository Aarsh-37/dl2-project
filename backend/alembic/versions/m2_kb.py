"""Alembic m2: KB tables learning_resources + question_bank (+ seed-safe uniques).

Import-light (stdlib + sqlalchemy + pgvector only). Rows are seeded by
scripts/seed_kb.py (idempotent) — never inside the revision.
"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB

revision = "m2_kb"
down_revision = "m1_core"
branch_labels = None
depends_on = None


def _uuid(name="id", pk=True):
    return sa.Column(
        name, sa.Uuid(as_uuid=True), primary_key=pk,
        server_default=sa.text("gen_random_uuid()"),
    )


def upgrade() -> None:
    op.create_table(
        "learning_resources",
        _uuid(),
        sa.Column("skill", sa.Text, nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("type", sa.String(10)),
        sa.Column("free", sa.Boolean, server_default="true"),
        sa.Column("embedding", Vector(384)),
        sa.UniqueConstraint("skill", "url", name="uq_learning_skill_url"),
    )
    op.create_table(
        "question_bank",
        _uuid(),
        sa.Column("skill", sa.Text),
        sa.Column("category", sa.Text),
        sa.Column("difficulty", sa.Text),
        sa.Column("q", sa.Text, nullable=False),
        sa.Column("ideal_answer", sa.Text),
        sa.Column("key_points", JSONB),
        sa.Column("embedding", Vector(384)),
        sa.UniqueConstraint("skill", "category", "q", name="uq_qbank"),
    )
    op.create_index("ix_learning_skill", "learning_resources", ["skill"])
    op.create_index("ix_qbank_skill", "question_bank", ["skill"])


def downgrade() -> None:
    op.drop_table("question_bank")
    op.drop_table("learning_resources")
