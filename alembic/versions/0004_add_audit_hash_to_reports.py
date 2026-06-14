"""Add audit_hash column to covenant_reports.

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-14
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "covenant_reports",
        sa.Column("audit_hash", sa.String(64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("covenant_reports", "audit_hash")
