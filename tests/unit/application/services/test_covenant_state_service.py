from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

from app.application.services.covenant_state_service import (
    initial_state,
    update_covenant_state,
)
from app.domain.covenant.state import CovenantStateStatus, FacilityCovenantState


def _existing_state(
    facility_id: str,
    numerator: str = "0",
    denominator: str = "0",
    status: CovenantStateStatus = CovenantStateStatus.NO_DATA,
) -> FacilityCovenantState:
    return FacilityCovenantState(
        id=uuid4(),
        facility_id=facility_id,
        accumulated_numerator=Decimal(numerator),
        accumulated_denominator=Decimal(denominator),
        effective_rate=Decimal("0"),
        covenant_status=status,
        last_updated=datetime.now(timezone.utc),
    )


def test_initial_state_has_no_data_status() -> None:
    state = initial_state("facility-a")
    assert state.facility_id == "facility-a"
    assert state.covenant_status == CovenantStateStatus.NO_DATA
    assert state.accumulated_numerator == Decimal("0")
    assert state.accumulated_denominator == Decimal("0")


def test_update_creates_state_when_none(monkeypatch) -> None:
    repo = MagicMock()
    repo.get_for_update.return_value = None

    state = update_covenant_state(
        repository=repo,
        facility_id="facility-a",
        contributions=[(Decimal("190000"), Decimal("9500"))],
        threshold=Decimal("22.00"),
    )

    repo.upsert.assert_called_once()
    assert state.accumulated_numerator == Decimal("190000")
    assert state.accumulated_denominator == Decimal("9500")
    assert state.effective_rate == Decimal("20.00")
    assert state.covenant_status == CovenantStateStatus.COMPLIANT


def test_update_accumulates_on_existing_state() -> None:
    repo = MagicMock()
    repo.get_for_update.return_value = _existing_state(
        "facility-a",
        numerator="100000",
        denominator="5000",
        status=CovenantStateStatus.COMPLIANT,
    )

    state = update_covenant_state(
        repository=repo,
        facility_id="facility-a",
        contributions=[(Decimal("90000"), Decimal("5000"))],
        threshold=Decimal("22.00"),
    )

    # 100000+90000=190000 / 5000+5000=10000 = 19.00 → COMPLIANT
    assert state.accumulated_numerator == Decimal("190000")
    assert state.accumulated_denominator == Decimal("10000")
    assert state.effective_rate == Decimal("19.00")
    assert state.covenant_status == CovenantStateStatus.COMPLIANT


def test_update_detects_breach() -> None:
    repo = MagicMock()
    repo.get_for_update.return_value = None

    state = update_covenant_state(
        repository=repo,
        facility_id="facility-a",
        contributions=[(Decimal("230000"), Decimal("10000"))],
        threshold=Decimal("22.00"),
    )

    # 230000/10000 = 23.00 > 22.00 → BREACH
    assert state.covenant_status == CovenantStateStatus.BREACH


def test_empty_contributions_preserves_state() -> None:
    existing = _existing_state(
        "facility-a",
        numerator="100000",
        denominator="5000",
        status=CovenantStateStatus.COMPLIANT,
    )
    repo = MagicMock()
    repo.get_for_update.return_value = existing

    state = update_covenant_state(
        repository=repo,
        facility_id="facility-a",
        contributions=[],
        threshold=Decimal("22.00"),
    )

    # No contributions → state unchanged
    assert state.accumulated_numerator == Decimal("100000")
    assert state.accumulated_denominator == Decimal("5000")
    assert state.covenant_status == CovenantStateStatus.COMPLIANT
    repo.upsert.assert_called_once()


def test_lock_is_always_acquired() -> None:
    repo = MagicMock()
    repo.get_for_update.return_value = None

    update_covenant_state(
        repository=repo,
        facility_id="facility-a",
        contributions=[],
        threshold=Decimal("22.00"),
    )

    repo.get_for_update.assert_called_once_with("facility-a")


def test_multiple_contributions_summed() -> None:
    repo = MagicMock()
    repo.get_for_update.return_value = None

    state = update_covenant_state(
        repository=repo,
        facility_id="facility-a",
        contributions=[
            (Decimal("95000"), Decimal("5000")),
            (Decimal("95000"), Decimal("5000")),
        ],
        threshold=Decimal("22.00"),
    )

    # (95000+95000)/(5000+5000) = 190000/10000 = 19.00
    assert state.accumulated_numerator == Decimal("190000")
    assert state.accumulated_denominator == Decimal("10000")
    assert state.effective_rate == Decimal("19.00")
