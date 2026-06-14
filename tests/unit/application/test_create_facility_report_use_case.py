from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.application.commands.create_facility_report import CreateFacilityReportCommand
from app.application.use_cases.create_facility_report import CreateFacilityReportUseCase
from app.domain.asset.record import AssetRecord
from app.domain.covenant.entities import CovenantReport, CovenantStatus
from app.domain.covenant.state import CovenantStateStatus, FacilityCovenantState
from app.domain.errors import CovenantCalculationError

_HASH = "a" * 64
_THRESHOLD = Decimal("22.00")


def _state(
    status: CovenantStateStatus = CovenantStateStatus.COMPLIANT,
    effective_rate: str = "19.00",
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


def _asset(external_id: str, eligible: bool = True) -> AssetRecord:
    return AssetRecord(
        id=uuid4(),
        facility_id="facility-a",
        external_id=external_id,
        status="open",
        amount=Decimal("1000"),
        is_eligible=eligible,
        is_eligible_asset=eligible,
        exclusion_reasons=[] if eligible else ["failed"],
        contribution_numerator=Decimal("20000") if eligible else None,
        contribution_denominator=Decimal("1000") if eligible else None,
        raw={},
        ingested_at=datetime.now(timezone.utc),
    )


def _existing_report(audit_hash: str = _HASH) -> CovenantReport:
    return CovenantReport(
        report_id=uuid4(),
        facility_id="facility-a",
        effective_rate=Decimal("19.00"),
        threshold=_THRESHOLD,
        status=CovenantStatus.COMPLIANT,
        total_assets=1,
        included_assets=["A1"],
        excluded_assets=[],
        computed_at=datetime.now(timezone.utc),
        correlation_id="corr-1",
        audit_hash=audit_hash,
        accumulated_numerator=Decimal("190000"),
        accumulated_denominator=Decimal("10000"),
    )


def _make_use_case(
    state: FacilityCovenantState | None = None,
    assets: list[AssetRecord] | None = None,
    latest_report: CovenantReport | None = None,
) -> CreateFacilityReportUseCase:
    state_repo = MagicMock()
    state_repo.get.return_value = state

    asset_repo = MagicMock()
    asset_repo.find_by_facility.return_value = assets or [_asset("A1")]

    calculator = MagicMock()
    calculator.threshold = _THRESHOLD
    registry = MagicMock()
    registry.get.return_value = calculator

    report_repo = MagicMock()
    report_repo.find_latest_by_facility.return_value = latest_report

    publisher = MagicMock()

    return CreateFacilityReportUseCase(
        state_repository=state_repo,
        asset_repository=asset_repo,
        registry=registry,
        report_repository=report_repo,
        publisher=publisher,
    )


def _cmd(force_new: bool = False) -> CreateFacilityReportCommand:
    return CreateFacilityReportCommand(
        facility_id="facility-a",
        correlation_id="corr-1",
        force_new=force_new,
    )


# ── NO_DATA guard ─────────────────────────────────────────────────────────────


def test_raises_when_no_state() -> None:
    use_case = _make_use_case(state=None)
    with pytest.raises(CovenantCalculationError, match="No asset data"):
        use_case.execute(_cmd())


def test_raises_when_state_is_no_data() -> None:
    use_case = _make_use_case(state=_state(CovenantStateStatus.NO_DATA))
    with pytest.raises(CovenantCalculationError, match="No asset data"):
        use_case.execute(_cmd())


# ── idempotency ───────────────────────────────────────────────────────────────


def test_returns_existing_report_when_hash_unchanged() -> None:
    existing = _existing_report(audit_hash=_HASH)
    use_case = _make_use_case(state=_state(), latest_report=existing)
    with patch(
        "app.application.use_cases.create_facility_report.compute_asset_hash",
        return_value=_HASH,
    ):
        result = use_case.execute(_cmd(force_new=False))

    assert result is existing
    use_case._report_repository.save.assert_not_called()
    use_case._publisher.publish.assert_not_called()


def test_creates_new_report_when_force_new() -> None:
    existing = _existing_report(audit_hash=_HASH)
    use_case = _make_use_case(state=_state(), latest_report=existing)

    with patch(
        "app.application.use_cases.create_facility_report.compute_asset_hash",
        return_value=_HASH,
    ):
        result = use_case.execute(_cmd(force_new=True))

    use_case._report_repository.save.assert_called_once()
    use_case._publisher.publish.assert_called_once()
    assert result.report_id != existing.report_id


def test_creates_new_report_when_hash_changed() -> None:
    existing = _existing_report(audit_hash="b" * 64)
    use_case = _make_use_case(state=_state(), latest_report=existing)

    with patch(
        "app.application.use_cases.create_facility_report.compute_asset_hash",
        return_value=_HASH,
    ):
        result = use_case.execute(_cmd(force_new=False))

    use_case._report_repository.save.assert_called_once()
    assert result.audit_hash == _HASH


def test_creates_new_report_when_no_previous_exists() -> None:
    use_case = _make_use_case(state=_state(), latest_report=None)

    with patch(
        "app.application.use_cases.create_facility_report.compute_asset_hash",
        return_value=_HASH,
    ):
        result = use_case.execute(_cmd())

    use_case._report_repository.save.assert_called_once()
    assert result.audit_hash == _HASH


# ── report content ────────────────────────────────────────────────────────────


def test_report_has_correct_status_for_compliant() -> None:
    use_case = _make_use_case(state=_state(CovenantStateStatus.COMPLIANT))
    with patch(
        "app.application.use_cases.create_facility_report.compute_asset_hash",
        return_value=_HASH,
    ):
        result = use_case.execute(_cmd())
    assert result.status == CovenantStatus.COMPLIANT


def test_report_has_correct_status_for_breach() -> None:
    use_case = _make_use_case(state=_state(CovenantStateStatus.BREACH))
    with patch(
        "app.application.use_cases.create_facility_report.compute_asset_hash",
        return_value=_HASH,
    ):
        result = use_case.execute(_cmd())
    assert result.status == CovenantStatus.BREACH


def test_report_separates_included_and_excluded() -> None:
    assets = [_asset("A1", eligible=True), _asset("A2", eligible=False)]
    use_case = _make_use_case(state=_state(), assets=assets)
    with patch(
        "app.application.use_cases.create_facility_report.compute_asset_hash",
        return_value=_HASH,
    ):
        result = use_case.execute(_cmd())

    assert result.included_assets == ["A1"]
    assert len(result.excluded_assets) == 1
    assert result.excluded_assets[0].external_id == "A2"


def test_report_threshold_comes_from_registry() -> None:
    use_case = _make_use_case(state=_state())
    with patch(
        "app.application.use_cases.create_facility_report.compute_asset_hash",
        return_value=_HASH,
    ):
        result = use_case.execute(_cmd())
    assert result.threshold == _THRESHOLD


def test_publisher_is_called() -> None:
    use_case = _make_use_case(state=_state())
    with patch(
        "app.application.use_cases.create_facility_report.compute_asset_hash",
        return_value=_HASH,
    ):
        use_case.execute(_cmd())
    use_case._publisher.publish.assert_called_once()
