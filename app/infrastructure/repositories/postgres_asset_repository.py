from datetime import timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.domain.asset.record import AssetRecord
from app.domain.asset.repository import AssetRepository
from app.domain.errors import CovenantPublicationError
from app.infrastructure.database.models import AssetModel


class PostgresAssetRepository(AssetRepository):
    """SQLAlchemy implementation of the AssetRepository domain interface."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save_batch(self, records: list[AssetRecord]) -> None:
        try:
            for record in records:
                model = AssetModel(
                    id=record.id,
                    facility_id=record.facility_id,
                    external_id=record.external_id,
                    status=record.status,
                    amount=record.amount,
                    is_eligible=record.is_eligible,
                    raw=record.raw,
                    ingested_at=record.ingested_at,
                )
                self._session.add(model)
            self._session.flush()
        except Exception as exc:
            raise CovenantPublicationError(f"Failed to persist assets: {exc}") from exc

    def find_existing_external_ids(
        self, facility_id: str, external_ids: list[str]
    ) -> set[str]:
        if not external_ids:
            return set()
        rows = (
            self._session.query(AssetModel.external_id)
            .filter(
                AssetModel.facility_id == facility_id,
                AssetModel.external_id.in_(external_ids),
            )
            .all()
        )
        return {row.external_id for row in rows}

    def find_by_facility(self, facility_id: str) -> list[AssetRecord]:
        rows = (
            self._session.query(AssetModel)
            .filter(AssetModel.facility_id == facility_id)
            .all()
        )
        return [_to_domain(row) for row in rows]


def _to_domain(model: AssetModel) -> AssetRecord:
    return AssetRecord(
        id=model.id,
        facility_id=model.facility_id,
        external_id=model.external_id,
        status=model.status,
        amount=Decimal(str(model.amount)),
        is_eligible=bool(model.is_eligible),
        raw=model.raw,
        ingested_at=(
            model.ingested_at
            if model.ingested_at.tzinfo is not None
            else model.ingested_at.replace(tzinfo=timezone.utc)
        ),
    )
