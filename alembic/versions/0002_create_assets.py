"""create assets table

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-13
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("facility_id", sa.String(), nullable=False),
        sa.Column("external_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("amount", sa.Numeric(20, 10), nullable=False),
        sa.Column("is_eligible", sa.Boolean(), nullable=False),
        sa.Column("raw", sa.JSON(), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "facility_id", "external_id", name="uq_asset_facility_external"
        ),
    )
    op.create_index("ix_assets_facility_id", "assets", ["facility_id"])


def downgrade() -> None:
    op.drop_index("ix_assets_facility_id", table_name="assets")
    op.drop_table("assets")
