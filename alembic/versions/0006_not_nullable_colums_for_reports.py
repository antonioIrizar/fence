"""not nullable for reports

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-14

"""

from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "covenant_reports",
        "audit_hash",
        existing_type=sa.VARCHAR(length=64),
        nullable=False,
    )
    op.alter_column(
        "covenant_reports",
        "accumulated_numerator",
        existing_type=sa.NUMERIC(precision=30, scale=10),
        nullable=False,
    )
    op.alter_column(
        "covenant_reports",
        "accumulated_denominator",
        existing_type=sa.NUMERIC(precision=30, scale=10),
        nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "covenant_reports",
        "accumulated_denominator",
        existing_type=sa.NUMERIC(precision=30, scale=10),
        nullable=True,
    )
    op.alter_column(
        "covenant_reports",
        "accumulated_numerator",
        existing_type=sa.NUMERIC(precision=30, scale=10),
        nullable=True,
    )
    op.alter_column(
        "covenant_reports",
        "audit_hash",
        existing_type=sa.VARCHAR(length=64),
        nullable=True,
    )
