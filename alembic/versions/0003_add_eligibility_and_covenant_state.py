"""Add eligibility columns to assets; create facility_covenant_state table.

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-13
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── assets table: new eligibility + contribution columns ─────────────────
    op.add_column(
        "assets",
        sa.Column(
            "is_eligible_asset", sa.Boolean(), nullable=False, server_default="false"
        ),
    )
    op.add_column(
        "assets",
        sa.Column("exclusion_reasons", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "assets",
        sa.Column("contribution_numerator", sa.Numeric(30, 10), nullable=True),
    )
    op.add_column(
        "assets",
        sa.Column("contribution_denominator", sa.Numeric(30, 10), nullable=True),
    )

    # ── facility_covenant_state table ─────────────────────────────────────────
    op.create_table(
        "facility_covenant_state",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("facility_id", sa.String(), nullable=False),
        sa.Column("accumulated_numerator", sa.Numeric(30, 10), nullable=False),
        sa.Column("accumulated_denominator", sa.Numeric(30, 10), nullable=False),
        sa.Column("effective_rate", sa.Numeric(20, 10), nullable=False),
        sa.Column("covenant_status", sa.String(), nullable=False),
        sa.Column("last_updated", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("facility_id", name="uq_facility_covenant_state_facility"),
    )
    op.create_index(
        "ix_facility_covenant_state_facility_id",
        "facility_covenant_state",
        ["facility_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_facility_covenant_state_facility_id",
        table_name="facility_covenant_state",
    )
    op.drop_table("facility_covenant_state")
    op.drop_column("assets", "contribution_denominator")
    op.drop_column("assets", "contribution_numerator")
    op.drop_column("assets", "exclusion_reasons")
    op.drop_column("assets", "is_eligible_asset")
