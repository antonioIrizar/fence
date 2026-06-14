from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

from app.application.use_cases.get_facility_state import GetFacilityStateUseCase
from app.domain.asset.record import AssetRecord
from app.domain.covenant.state import CovenantStateStatus, FacilityCovenantState


def _state(facility_id: str = "facility-a") -> FacilityCovenantState:
    return FacilityCovenantState(
        id=uuid4(),
        facility_id=facility_id,
        accumulated_numerator=Decimal("190000"),
        accumulated_denominator=Decimal("10000"),
        effective_rate=Decimal("19.00"),
        covenant_status=CovenantStateStatus.COMPLIANT,
        last_updated=datetime.now(timezone.utc),
    )


def _record(
    external_id: str,
    is_eligible_asset: bool = True,
    exclusion_reasons: list[str] | None = None,
) -> AssetRecord:
    return AssetRecord(
        id=uuid4(),
        facility_id="facility-a",
        external_id=external_id,
        status="open",
        amount=Decimal("1000"),
        is_eligible=is_eligible_asset,
        is_eligible_asset=is_eligible_asset,
        exclusion_reasons=exclusion_reasons or [],
        raw={},
        ingested_at=datetime.now(timezone.utc),
    )


def _make_use_case(
    state: FacilityCovenantState | None = None,
    assets: list[AssetRecord] | None = None,
) -> tuple[GetFacilityStateUseCase, MagicMock, MagicMock]:
    state_repo = MagicMock()
    state_repo.get.return_value = state

    asset_repo = MagicMock()
    asset_repo.find_by_facility.return_value = assets or []

    use_case = GetFacilityStateUseCase(
        state_repository=state_repo,
        asset_repository=asset_repo,
    )
    return use_case, state_repo, asset_repo


def test_returns_existing_covenant_state() -> None:
    existing = _state()
    use_case, _, _ = _make_use_case(state=existing)

    result = use_case.execute("facility-a")

    assert result.covenant_state is existing
    assert result.covenant_state.covenant_status == CovenantStateStatus.COMPLIANT


def test_returns_initial_state_when_no_covenant_state() -> None:
    use_case, state_repo, _ = _make_use_case(state=None)
    state_repo.get.return_value = None

    result = use_case.execute("facility-a")

    assert result.covenant_state.facility_id == "facility-a"
    assert result.covenant_state.covenant_status == CovenantStateStatus.NO_DATA


def test_separates_included_and_excluded_assets() -> None:
    assets = [
        _record("A1", is_eligible_asset=True),
        _record("A2", is_eligible_asset=False, exclusion_reasons=["status wrong"]),
        _record("A3", is_eligible_asset=True),
    ]
    use_case, _, _ = _make_use_case(state=_state(), assets=assets)

    result = use_case.execute("facility-a")

    assert result.included_assets == ["A1", "A3"]
    assert len(result.excluded_assets) == 1
    assert result.excluded_assets[0].external_id == "A2"
    assert result.excluded_assets[0].reasons == ["status wrong"]


def test_total_assets_is_sum_of_included_and_excluded() -> None:
    assets = [
        _record("A1", is_eligible_asset=True),
        _record("A2", is_eligible_asset=False, exclusion_reasons=["x"]),
        _record("A3", is_eligible_asset=False, exclusion_reasons=["y", "z"]),
    ]
    use_case, _, _ = _make_use_case(state=_state(), assets=assets)

    result = use_case.execute("facility-a")

    assert result.total_assets == 3
    assert len(result.included_assets) == 1
    assert len(result.excluded_assets) == 2


def test_no_assets_returns_empty_lists() -> None:
    use_case, _, _ = _make_use_case(state=_state(), assets=[])

    result = use_case.execute("facility-a")

    assert result.included_assets == []
    assert result.excluded_assets == []
    assert result.total_assets == 0


def test_all_eligible_no_excluded() -> None:
    assets = [_record(f"A{i}", is_eligible_asset=True) for i in range(3)]
    use_case, _, _ = _make_use_case(state=_state(), assets=assets)

    result = use_case.execute("facility-a")

    assert len(result.included_assets) == 3
    assert result.excluded_assets == []


def test_all_ineligible_no_included() -> None:
    assets = [
        _record("A1", is_eligible_asset=False, exclusion_reasons=["r1"]),
        _record("A2", is_eligible_asset=False, exclusion_reasons=["r2", "r3"]),
    ]
    use_case, _, _ = _make_use_case(state=_state(), assets=assets)

    result = use_case.execute("facility-a")

    assert result.included_assets == []
    assert len(result.excluded_assets) == 2


def test_queries_correct_facility() -> None:
    use_case, state_repo, asset_repo = _make_use_case(state=_state("facility-b"))

    use_case.execute("facility-b")

    state_repo.get.assert_called_once_with("facility-b")
    asset_repo.find_by_facility.assert_called_once_with("facility-b")


def test_excluded_asset_preserves_all_reasons() -> None:
    assets = [
        _record(
            "A1",
            is_eligible_asset=False,
            exclusion_reasons=["status != open", "loan_status != current"],
        )
    ]
    use_case, _, _ = _make_use_case(state=_state(), assets=assets)

    result = use_case.execute("facility-a")

    assert result.excluded_assets[0].reasons == [
        "status != open",
        "loan_status != current",
    ]
