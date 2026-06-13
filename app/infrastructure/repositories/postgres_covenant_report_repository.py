from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.domain.covenant.entities import CovenantReport, CovenantStatus, ExcludedAsset
from app.domain.covenant.repository import CovenantReportRepository
from app.domain.errors import CovenantPublicationError
from app.infrastructure.database.models import CovenantReportModel


class PostgresCovenantReportRepository(CovenantReportRepository):
    """Persists covenant reports to PostgreSQL. Each save creates a new row."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, report: CovenantReport) -> None:
        try:
            model = CovenantReportModel(
                id=report.report_id,
                facility_id=report.facility_id,
                effective_rate=str(report.effective_rate),
                threshold=str(report.threshold),
                status=report.status.value,
                total_assets=report.total_assets,
                included_assets=report.included_assets,
                excluded_assets=[
                    {"external_id": e.external_id, "reasons": e.reasons}
                    for e in report.excluded_assets
                ],
                computed_at=report.computed_at,
                correlation_id=report.correlation_id,
            )
            self._session.add(model)
            self._session.flush()
        except Exception as e:
            raise CovenantPublicationError(
                f"Failed to save covenant report: {e}"
            ) from e

    def find_by_id(self, report_id: UUID) -> Optional[CovenantReport]:
        model = self._session.get(CovenantReportModel, report_id)
        if model is None:
            return None
        return self._to_domain(model)

    def find_by_facility(self, facility_id: str) -> list[CovenantReport]:
        models = (
            self._session.query(CovenantReportModel)
            .filter(CovenantReportModel.facility_id == facility_id)
            .order_by(CovenantReportModel.computed_at.desc())
            .all()
        )
        return [self._to_domain(m) for m in models]

    @staticmethod
    def _to_domain(model: CovenantReportModel) -> CovenantReport:
        return CovenantReport(
            report_id=model.id,
            facility_id=model.facility_id,
            effective_rate=Decimal(str(model.effective_rate)),
            threshold=Decimal(str(model.threshold)),
            status=CovenantStatus(model.status),
            total_assets=model.total_assets,
            included_assets=model.included_assets,
            excluded_assets=[
                ExcludedAsset(
                    external_id=e["external_id"],
                    reasons=e["reasons"],
                )
                for e in model.excluded_assets
            ],
            computed_at=model.computed_at,
            correlation_id=model.correlation_id,
        )
