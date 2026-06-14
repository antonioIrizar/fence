"""add accumulated_numerator and accumulated_denominator to covenant_reports

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-14

Seals the exact covenant-state accumulated totals inside each report so that
old reports can be verified accurately even after new assets are ingested.
The sum of per-asset contribution_numerator values in the DB is not identical
to the in-memory Decimal sum used when the state was built (Numeric(30,10)
truncation means individually-stored values sum differently than the full-
precision accumulation). Storing the state snapshot removes that discrepancy.
"""

from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "covenant_reports",
        sa.Column("accumulated_numerator", sa.Numeric(30, 10), nullable=True),
    )
    op.add_column(
        "covenant_reports",
        sa.Column("accumulated_denominator", sa.Numeric(30, 10), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("covenant_reports", "accumulated_numerator")
    op.drop_column("covenant_reports", "accumulated_denominator")
