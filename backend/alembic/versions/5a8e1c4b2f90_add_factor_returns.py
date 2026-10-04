"""add factor_returns

Revision ID: 5a8e1c4b2f90
Revises: 3c1f2a9d7b10
Create Date: 2026-10-04 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by alembic
revision: str = "5a8e1c4b2f90"
down_revision: str | Sequence[str] | None = "3c1f2a9d7b10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "factor_returns",
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("mkt_rf", sa.Float(), nullable=False),
        sa.Column("smb", sa.Float(), nullable=False),
        sa.Column("hml", sa.Float(), nullable=False),
        sa.Column("rmw", sa.Float(), nullable=False),
        sa.Column("cma", sa.Float(), nullable=False),
        sa.Column("mom", sa.Float(), nullable=False),
        sa.Column("rf", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("date"),
    )
    op.create_table(
        "factor_fetch",
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("attempted_at", sa.DateTime(), nullable=False),
        sa.Column("succeeded", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("source"),
    )


def downgrade() -> None:
    op.drop_table("factor_fetch")
    op.drop_table("factor_returns")
