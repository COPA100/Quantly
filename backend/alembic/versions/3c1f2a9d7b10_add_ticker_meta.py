"""add ticker_meta

Revision ID: 3c1f2a9d7b10
Revises: 99b22646355f
Create Date: 2026-10-04 17:40:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by alembic
revision: str = "3c1f2a9d7b10"
down_revision: str | Sequence[str] | None = "99b22646355f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ticker_meta",
        sa.Column("ticker", sa.String(length=10), nullable=False),
        sa.Column("backfilled_from", sa.Date(), nullable=False),
        sa.PrimaryKeyConstraint("ticker"),
    )


def downgrade() -> None:
    op.drop_table("ticker_meta")
