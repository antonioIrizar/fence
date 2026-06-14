from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from app.domain.covenant.state import CovenantStateStatus, FacilityCovenantState


def test_initial_no_data_state() -> None:
    state = FacilityCovenantState(
        id=uuid4(),
        facility_id="facility-a",
        accumulated_numerator=Decimal("0"),
        accumulated_denominator=Decimal("0"),
        effective_rate=Decimal("0"),
        covenant_status=CovenantStateStatus.NO_DATA,
        last_updated=datetime.now(timezone.utc),
    )
    assert state.covenant_status == CovenantStateStatus.NO_DATA
    assert state.accumulated_denominator == Decimal("0")


def test_compliant_state() -> None:
    state = FacilityCovenantState(
        id=uuid4(),
        facility_id="facility-a",
        accumulated_numerator=Decimal("190000"),
        accumulated_denominator=Decimal("9500"),
        effective_rate=Decimal("20.00"),
        covenant_status=CovenantStateStatus.COMPLIANT,
        last_updated=datetime.now(timezone.utc),
    )
    assert state.covenant_status == CovenantStateStatus.COMPLIANT
    assert state.effective_rate == Decimal("20.00")


def test_breach_state() -> None:
    state = FacilityCovenantState(
        id=uuid4(),
        facility_id="facility-a",
        accumulated_numerator=Decimal("230000"),
        accumulated_denominator=Decimal("9500"),
        effective_rate=Decimal("24.21"),
        covenant_status=CovenantStateStatus.BREACH,
        last_updated=datetime.now(timezone.utc),
    )
    assert state.covenant_status == CovenantStateStatus.BREACH


def test_status_enum_values() -> None:
    assert CovenantStateStatus.COMPLIANT == "COMPLIANT"
    assert CovenantStateStatus.BREACH == "BREACH"
    assert CovenantStateStatus.NO_DATA == "NO_DATA"
