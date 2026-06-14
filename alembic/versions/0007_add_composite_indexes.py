"""Add composite indexes for facility+timestamp queries.

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-14

Replaces the single-column ix_covenant_reports_facility_id with a composite
(facility_id, computed_at) index — the primary access pattern is always
scoped to a facility and ordered by report date.

Adds a parallel composite (facility_id, ingested_at) index on assets for the
same reason: report generation and verification filter by facility and order
by ingestion time.
"""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # covenant_reports: drop redundant single-column index, add composite one
    op.drop_index("ix_covenant_reports_facility_id", table_name="covenant_reports")
    op.create_index(
        "ix_covenant_reports_facility_computed",
        "covenant_reports",
        ["facility_id", "computed_at"],
    )

    # assets: add composite index alongside the existing single-column one
    op.create_index(
        "ix_assets_facility_ingested",
        "assets",
        ["facility_id", "ingested_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_assets_facility_ingested", table_name="assets")
    op.drop_index(
        "ix_covenant_reports_facility_computed", table_name="covenant_reports"
    )
    op.create_index(
        "ix_covenant_reports_facility_id", "covenant_reports", ["facility_id"]
    )
