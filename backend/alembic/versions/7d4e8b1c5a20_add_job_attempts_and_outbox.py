"""add job attempts and outbox

Revision ID: 7d4e8b1c5a20
Revises: 3c1f2a9d7b10
Create Date: 2026-10-04 19:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by alembic
revision: str = "7d4e8b1c5a20"
down_revision: str | Sequence[str] | None = "3c1f2a9d7b10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("attempts", sa.Integer(), server_default="0", nullable=False))
    op.add_column("jobs", sa.Column("last_error", sa.Text(), nullable=True))
    op.add_column("jobs", sa.Column("run_token", sa.String(length=36), nullable=True))

    op.create_table(
        "outbox",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=50), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_outbox_published_at", "outbox", ["published_at"])


def downgrade() -> None:
    op.drop_index("ix_outbox_published_at", table_name="outbox")
    op.drop_table("outbox")
    with op.batch_alter_table("jobs") as batch:
        batch.drop_column("run_token")
        batch.drop_column("last_error")
        batch.drop_column("attempts")
