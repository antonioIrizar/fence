from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class AssetModel(Base):
    """
    Persisted raw asset record for a facility.

    `raw` holds the complete original payload for auditability.
    The (facility_id, external_id) pair is unique — duplicate ingestion is rejected.
    """

    __tablename__ = "assets"
    __table_args__ = (
        UniqueConstraint(
            "facility_id", "external_id", name="uq_asset_facility_external"
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    facility_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    external_id: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[str] = mapped_column(Numeric(20, 10), nullable=False)
    is_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    raw: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class CovenantReportModel(Base):
    """
    Immutable persistence model for covenant reports.
    Each row represents one calculation event — rows are never updated.
    """

    __tablename__ = "covenant_reports"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    facility_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    effective_rate: Mapped[str] = mapped_column(Numeric(20, 10), nullable=False)
    threshold: Mapped[str] = mapped_column(Numeric(20, 10), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    total_assets: Mapped[int] = mapped_column(Integer, nullable=False)
    included_assets: Mapped[list[Any]] = mapped_column(JSON, nullable=False)
    excluded_assets: Mapped[list[Any]] = mapped_column(JSON, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    correlation_id: Mapped[str] = mapped_column(String, nullable=False)
