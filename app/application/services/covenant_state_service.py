from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from uuid import uuid4

from app.domain.covenant.state import CovenantStateStatus, FacilityCovenantState
from app.domain.covenant.state_repository import FacilityCovenantStateRepository
from app.domain.errors import CovenantCalculationError

_TWO_PLACES = Decimal("0.01")


def initial_state(facility_id: str) -> FacilityCovenantState:
    """Return a zero-valued covenant state for a facility with no ingested assets."""
    return FacilityCovenantState(
        id=uuid4(),
        facility_id=facility_id,
        accumulated_numerator=Decimal("0"),
        accumulated_denominator=Decimal("0"),
        effective_rate=Decimal("0"),
        covenant_status=CovenantStateStatus.NO_DATA,
        last_updated=datetime.now(timezone.utc),
    )


def _recompute(
    state: FacilityCovenantState,
    delta_numerator: Decimal,
    delta_denominator: Decimal,
    threshold: Decimal,
) -> FacilityCovenantState:
    """
    Return a new FacilityCovenantState with the given delta accumulated.

    INSERT lifecycle: delta = full asset contribution (numerator, denominator).
    Future UPDATE lifecycle: delta = new_contribution − old_contribution.
    """
    new_numerator = state.accumulated_numerator + delta_numerator
    new_denominator = state.accumulated_denominator + delta_denominator
    if new_denominator == Decimal("0"):
        raise CovenantCalculationError(
            f"Covenant denominator is zero for facility '{state.facility_id}' — "
            "all eligible assets have a zero outstanding amount."
        )
    effective_rate = (new_numerator / new_denominator).quantize(
        _TWO_PLACES, rounding=ROUND_HALF_UP
    )
    status = (
        CovenantStateStatus.COMPLIANT
        if effective_rate < threshold
        else CovenantStateStatus.BREACH
    )
    return FacilityCovenantState(
        id=state.id,
        facility_id=state.facility_id,
        accumulated_numerator=new_numerator,
        accumulated_denominator=new_denominator,
        effective_rate=effective_rate,
        covenant_status=status,
        last_updated=datetime.now(timezone.utc),
    )


def update_covenant_state(
    repository: FacilityCovenantStateRepository,
    facility_id: str,
    contributions: list[tuple[Decimal, Decimal]],
    threshold: Decimal,
) -> FacilityCovenantState:
    """
    Accumulate new asset contributions into the facility covenant state.

    When contributions is non-empty: acquires a SELECT FOR UPDATE lock to
    prevent concurrent ingest tasks from producing incorrect accumulated
    totals, recomputes the state, and persists it.

    When contributions is empty: reads without a lock and skips the write,
    returning the existing state (or a zero-valued initial state) unchanged.

    A contribution is a (numerator, denominator) pair pre-computed by the
    FacilityCalculator for one eligible asset.
    """
    if not contributions:
        return repository.get(facility_id) or initial_state(facility_id)

    state = repository.get_for_update(facility_id) or initial_state(facility_id)
    delta_num = sum((n for n, _ in contributions), Decimal("0"))
    delta_den = sum((d for _, d in contributions), Decimal("0"))
    state = _recompute(state, delta_num, delta_den, threshold)
    repository.upsert(state)
    return state
