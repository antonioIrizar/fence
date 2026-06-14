from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from app.domain.asset.record import AssetRecord
from app.domain.covenant.audit import compute_asset_hash
from app.domain.covenant.state import CovenantStateStatus, FacilityCovenantState


def _state(
    effective_rate: str = "19.00",
    status: CovenantStateStatus = CovenantStateStatus.COMPLIANT,
) -> FacilityCovenantState:
    return FacilityCovenantState(
        id=uuid4(),
        facility_id="facility-a",
        accumulated_numerator=Decimal("190000"),
        accumulated_denominator=Decimal("10000"),
        effective_rate=Decimal(effective_rate),
        covenant_status=status,
        last_updated=datetime.now(timezone.utc),
    )


def _asset(
    external_id: str,
    amount: str = "1000",
    is_eligible: bool = True,
    reasons: list[str] | None = None,
    numerator: str | None = "20000",
    denominator: str | None = "1000",
) -> AssetRecord:
    return AssetRecord(
        id=uuid4(),
        facility_id="facility-a",
        external_id=external_id,
        status="open",
        amount=Decimal(amount),
        is_eligible=is_eligible,
        is_eligible_asset=is_eligible,
        exclusion_reasons=reasons or [],
        contribution_numerator=Decimal(numerator) if numerator else None,
        contribution_denominator=Decimal(denominator) if denominator else None,
        raw={},
        ingested_at=datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc),
    )


def test_returns_hex_string_of_64_chars() -> None:
    h = compute_asset_hash("facility-a", [_asset("A1")], _state())
    assert isinstance(h, str)
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_same_input_produces_same_hash() -> None:
    assets = [_asset("A1"), _asset("A2")]
    state = _state()
    h1 = compute_asset_hash("facility-a", assets, state)
    h2 = compute_asset_hash("facility-a", assets, state)
    assert h1 == h2


def test_asset_order_does_not_affect_hash() -> None:
    a1, a2 = _asset("A1"), _asset("A2")
    state = _state()
    h_forward = compute_asset_hash("facility-a", [a1, a2], state)
    h_reverse = compute_asset_hash("facility-a", [a2, a1], state)
    assert h_forward == h_reverse


def test_different_facility_produces_different_hash() -> None:
    assets = [_asset("A1")]
    state = _state()
    h_a = compute_asset_hash("facility-a", assets, state)
    h_b = compute_asset_hash("facility-b", assets, state)
    assert h_a != h_b


def test_changed_amount_produces_different_hash() -> None:
    state = _state()
    h1 = compute_asset_hash("facility-a", [_asset("A1", amount="1000")], state)
    h2 = compute_asset_hash("facility-a", [_asset("A1", amount="2000")], state)
    assert h1 != h2


def test_changed_eligibility_produces_different_hash() -> None:
    state = _state()
    h1 = compute_asset_hash("facility-a", [_asset("A1", is_eligible=True)], state)
    h2 = compute_asset_hash(
        "facility-a",
        [
            _asset(
                "A1",
                is_eligible=False,
                reasons=["failed"],
                numerator=None,
                denominator=None,
            )
        ],
        state,
    )
    assert h1 != h2


def test_changed_effective_rate_produces_different_hash() -> None:
    assets = [_asset("A1")]
    h1 = compute_asset_hash("facility-a", assets, _state(effective_rate="19.00"))
    h2 = compute_asset_hash("facility-a", assets, _state(effective_rate="23.00"))
    assert h1 != h2


def test_changed_covenant_status_produces_different_hash() -> None:
    assets = [_asset("A1")]
    h1 = compute_asset_hash(
        "facility-a", assets, _state(status=CovenantStateStatus.COMPLIANT)
    )
    h2 = compute_asset_hash(
        "facility-a", assets, _state(status=CovenantStateStatus.BREACH)
    )
    assert h1 != h2


def test_exclusion_reason_order_does_not_affect_hash() -> None:
    state = _state()
    a1 = _asset(
        "A1", is_eligible=False, reasons=["r1", "r2"], numerator=None, denominator=None
    )
    a2 = _asset(
        "A1", is_eligible=False, reasons=["r2", "r1"], numerator=None, denominator=None
    )
    h1 = compute_asset_hash("facility-a", [a1], state)
    h2 = compute_asset_hash("facility-a", [a2], state)
    assert h1 == h2


def test_empty_assets_produces_stable_hash() -> None:
    state = _state()
    h1 = compute_asset_hash("facility-a", [], state)
    h2 = compute_asset_hash("facility-a", [], state)
    assert h1 == h2
    assert len(h1) == 64
