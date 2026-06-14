from datetime import timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.domain.covenant.state import CovenantStateStatus, FacilityCovenantState
from app.domain.covenant.state_repository import FacilityCovenantStateRepository
from app.infrastructure.database.models import FacilityCovenantStateModel


class PostgresFacilityCovenantStateRepository(FacilityCovenantStateRepository):
    """
    SQLAlchemy implementation of FacilityCovenantStateRepository.

    `get_for_update` issues SELECT … FOR UPDATE to acquire a row-level
    exclusive lock, preventing concurrent ingestion tasks from producing
    incorrect accumulated totals.  SQLite (used in tests) silently ignores the
    FOR UPDATE clause — correctness under concurrency is guaranteed only in
    PostgreSQL.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, facility_id: str) -> Optional[FacilityCovenantState]:
        row = (
            self._session.query(FacilityCovenantStateModel)
            .filter_by(facility_id=facility_id)
            .first()
        )
        return _to_domain(row) if row else None

    def get_for_update(self, facility_id: str) -> Optional[FacilityCovenantState]:
        row = (
            self._session.query(FacilityCovenantStateModel)
            .filter_by(facility_id=facility_id)
            .with_for_update()
            .first()
        )
        return _to_domain(row) if row else None

    def upsert(self, state: FacilityCovenantState) -> None:
        existing = (
            self._session.query(FacilityCovenantStateModel)
            .filter_by(facility_id=state.facility_id)
            .first()
        )
        if existing:
            existing.accumulated_numerator = state.accumulated_numerator
            existing.accumulated_denominator = state.accumulated_denominator
            existing.effective_rate = state.effective_rate
            existing.covenant_status = state.covenant_status.value
            existing.last_updated = state.last_updated
        else:
            self._session.add(
                FacilityCovenantStateModel(
                    id=state.id,
                    facility_id=state.facility_id,
                    accumulated_numerator=state.accumulated_numerator,
                    accumulated_denominator=state.accumulated_denominator,
                    effective_rate=state.effective_rate,
                    covenant_status=state.covenant_status.value,
                    last_updated=state.last_updated,
                )
            )
        self._session.flush()


def _to_domain(model: FacilityCovenantStateModel) -> FacilityCovenantState:
    last_updated = model.last_updated
    if last_updated.tzinfo is None:
        last_updated = last_updated.replace(tzinfo=timezone.utc)
    return FacilityCovenantState(
        id=model.id,
        facility_id=model.facility_id,
        accumulated_numerator=Decimal(str(model.accumulated_numerator)),
        accumulated_denominator=Decimal(str(model.accumulated_denominator)),
        effective_rate=Decimal(str(model.effective_rate)),
        covenant_status=CovenantStateStatus(model.covenant_status),
        last_updated=last_updated,
    )
