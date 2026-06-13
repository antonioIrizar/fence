"""create covenant reports table

Revision ID: 0001
Revises:
Create Date: 2026-06-12

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "covenant_reports",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            primary_key=True,
        ),
        sa.Column("facility_id", sa.String(), nullable=False),
        sa.Column("effective_rate", sa.Numeric(20, 10), nullable=False),
        sa.Column("threshold", sa.Numeric(20, 10), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("total_assets", sa.Integer(), nullable=False),
        sa.Column("included_assets", sa.JSON(), nullable=False),
        sa.Column("excluded_assets", sa.JSON(), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("correlation_id", sa.String(), nullable=False),
    )
    op.create_index(
        "ix_covenant_reports_facility_id",
        "covenant_reports",
        ["facility_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_covenant_reports_facility_id", table_name="covenant_reports")
    op.drop_table("covenant_reports")
