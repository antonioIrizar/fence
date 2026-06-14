from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from app.domain.covenant.state import CovenantStateStatus, FacilityCovenantState
from app.infrastructure.repositories.postgres_facility_covenant_state_repository import (  # noqa: E501
    PostgresFacilityCovenantStateRepository,
)


def _make_state(facility_id: str, rate: str = "20.00") -> FacilityCovenantState:
    return FacilityCovenantState(
        id=uuid4(),
        facility_id=facility_id,
        accumulated_numerator=Decimal("190000"),
        accumulated_denominator=Decimal("9500"),
        effective_rate=Decimal(rate),
        covenant_status=CovenantStateStatus.COMPLIANT,
        last_updated=datetime.now(timezone.utc),
    )


def test_upsert_creates_new_state(db_session) -> None:
    repo = PostgresFacilityCovenantStateRepository(db_session)
    state = _make_state("fac-new-1")
    repo.upsert(state)

    result = repo.get("fac-new-1")
    assert result is not None
    assert result.facility_id == "fac-new-1"
    assert result.effective_rate == Decimal("20.00")
    assert result.covenant_status == CovenantStateStatus.COMPLIANT


def test_upsert_updates_existing_state(db_session) -> None:
    repo = PostgresFacilityCovenantStateRepository(db_session)
    state = _make_state("fac-upd-1", rate="19.00")
    repo.upsert(state)

    updated = FacilityCovenantState(
        id=state.id,
        facility_id="fac-upd-1",
        accumulated_numerator=Decimal("250000"),
        accumulated_denominator=Decimal("10000"),
        effective_rate=Decimal("25.00"),
        covenant_status=CovenantStateStatus.BREACH,
        last_updated=datetime.now(timezone.utc),
    )
    repo.upsert(updated)

    result = repo.get("fac-upd-1")
    assert result is not None
    assert result.effective_rate == Decimal("25.00")
    assert result.covenant_status == CovenantStateStatus.BREACH
    assert result.accumulated_numerator == Decimal("250000")


def test_get_returns_none_when_missing(db_session) -> None:
    repo = PostgresFacilityCovenantStateRepository(db_session)
    result = repo.get("nonexistent-facility")
    assert result is None


def test_get_for_update_returns_state(db_session) -> None:
    repo = PostgresFacilityCovenantStateRepository(db_session)
    state = _make_state("fac-lock-1")
    repo.upsert(state)

    locked = repo.get_for_update("fac-lock-1")
    assert locked is not None
    assert locked.facility_id == "fac-lock-1"


def test_get_for_update_returns_none_when_missing(db_session) -> None:
    repo = PostgresFacilityCovenantStateRepository(db_session)
    result = repo.get_for_update("nonexistent-fac-lock")
    assert result is None


def test_upsert_preserves_numerator_and_denominator(db_session) -> None:
    repo = PostgresFacilityCovenantStateRepository(db_session)
    state = FacilityCovenantState(
        id=uuid4(),
        facility_id="fac-nums-1",
        accumulated_numerator=Decimal("12345.6789"),
        accumulated_denominator=Decimal("999.01"),
        effective_rate=Decimal("12.36"),
        covenant_status=CovenantStateStatus.COMPLIANT,
        last_updated=datetime.now(timezone.utc),
    )
    repo.upsert(state)

    result = repo.get("fac-nums-1")
    assert result is not None
    # Allow minor rounding from Numeric(30, 10)
    assert abs(result.accumulated_numerator - Decimal("12345.6789")) < Decimal("0.0001")
    assert abs(result.accumulated_denominator - Decimal("999.01")) < Decimal("0.0001")
