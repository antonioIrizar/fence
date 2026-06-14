from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.application.use_cases.verify_report import VerifyReportUseCase
from app.domain.asset.record import AssetRecord
from app.domain.covenant.entities import CovenantReport, CovenantStatus
from app.domain.errors import CovenantCalculationError

_HASH = "a" * 64
_OTHER_HASH = "b" * 64
_REPORT_ID = uuid4()
_COMPUTED_AT = datetime(2026, 1, 10, 12, 0, 0, tzinfo=timezone.utc)


def _report(
    audit_hash: str | None = _HASH,
    accumulated_numerator: Decimal | None = Decimal("190000"),
    accumulated_denominator: Decimal | None = Decimal("10000"),
) -> CovenantReport:
    return CovenantReport(
        report_id=_REPORT_ID,
        facility_id="facility-a",
        effective_rate=Decimal("19.00"),
        threshold=Decimal("22.00"),
        status=CovenantStatus.COMPLIANT,
        total_assets=1,
        included_assets=["A1"],
        excluded_assets=[],
        computed_at=_COMPUTED_AT,
        correlation_id="corr-1",
        audit_hash=audit_hash,
        accumulated_numerator=accumulated_numerator,
        accumulated_denominator=accumulated_denominator,
    )


def _asset(
    external_id: str = "A1",
    eligible: bool = True,
    ingested_at: datetime | None = None,
) -> AssetRecord:
    return AssetRecord(
        id=uuid4(),
        facility_id="facility-a",
        external_id=external_id,
        status="open",
        amount=Decimal("1000"),
        is_eligible=eligible,
        is_eligible_asset=eligible,
        exclusion_reasons=[] if eligible else ["failed"],
        contribution_numerator=Decimal("19000") if eligible else None,
        contribution_denominator=Decimal("1000") if eligible else None,
        raw={},
        ingested_at=ingested_at or _COMPUTED_AT,
    )


def _make_use_case(
    report: CovenantReport | None = None,
    assets_at_time: list[AssetRecord] | None = None,
) -> VerifyReportUseCase:
    report_repo = MagicMock()
    report_repo.find_by_id.return_value = report

    asset_repo = MagicMock()
    asset_repo.find_by_facility_at.return_value = assets_at_time or []

    return VerifyReportUseCase(
        report_repository=report_repo,
        asset_repository=asset_repo,
    )


# ── error cases ───────────────────────────────────────────────────────────────


def test_raises_when_report_not_found() -> None:
    use_case = _make_use_case(report=None)
    with pytest.raises(CovenantCalculationError, match="not found"):
        use_case.execute("facility-a", _REPORT_ID)


def test_raises_when_report_belongs_to_different_facility() -> None:
    """IDOR guard: a report from facility-b must not be readable via facility-a."""
    other_report = CovenantReport(
        report_id=_REPORT_ID,
        facility_id="facility-b",
        effective_rate=Decimal("19.00"),
        threshold=Decimal("22.00"),
        status=CovenantStatus.COMPLIANT,
        total_assets=1,
        included_assets=["A1"],
        excluded_assets=[],
        computed_at=_COMPUTED_AT,
        correlation_id="corr-1",
        audit_hash=_HASH,
        accumulated_numerator=Decimal("190000"),
        accumulated_denominator=Decimal("10000"),
    )
    use_case = _make_use_case(report=other_report)
    with pytest.raises(CovenantCalculationError, match="does not belong"):
        use_case.execute("facility-a", _REPORT_ID)


# ── snapshot query ────────────────────────────────────────────────────────────


def test_queries_assets_at_report_computed_at() -> None:
    """The repository must be queried with the report's computed_at timestamp,
    not the current time, so new assets ingested after the report do not
    affect the recomputed hash."""
    use_case = _make_use_case(report=_report(), assets_at_time=[_asset()])
    with patch(
        "app.application.use_cases.verify_report.compute_asset_hash",
        return_value=_HASH,
    ):
        use_case.execute("facility-a", _REPORT_ID)

    use_case._asset_repository.find_by_facility_at.assert_called_once_with(
        "facility-a", _COMPUTED_AT
    )


# ── valid hash ────────────────────────────────────────────────────────────────


def test_returns_valid_when_hash_matches() -> None:
    use_case = _make_use_case(
        report=_report(audit_hash=_HASH), assets_at_time=[_asset()]
    )
    with patch(
        "app.application.use_cases.verify_report.compute_asset_hash",
        return_value=_HASH,
    ):
        result = use_case.execute("facility-a", _REPORT_ID)

    assert result.is_valid is True
    assert result.stored_hash == _HASH
    assert result.computed_hash == _HASH


def test_returns_invalid_when_hash_differs() -> None:
    use_case = _make_use_case(
        report=_report(audit_hash=_HASH), assets_at_time=[_asset()]
    )
    with patch(
        "app.application.use_cases.verify_report.compute_asset_hash",
        return_value=_OTHER_HASH,
    ):
        result = use_case.execute("facility-a", _REPORT_ID)

    assert result.is_valid is False
    assert result.stored_hash == _HASH
    assert result.computed_hash == _OTHER_HASH


def test_result_carries_report_and_facility_id() -> None:
    use_case = _make_use_case(report=_report(), assets_at_time=[])
    with patch(
        "app.application.use_cases.verify_report.compute_asset_hash",
        return_value=_HASH,
    ):
        result = use_case.execute("facility-a", _REPORT_ID)

    assert result.report_id == _REPORT_ID
    assert result.facility_id == "facility-a"


def test_valid_after_new_assets_ingested() -> None:
    """Old report must still verify as valid even if new assets have been
    added since the report was sealed. Only assets up to computed_at count."""
    old_asset = _asset("A1", ingested_at=_COMPUTED_AT)
    new_asset = _asset(
        "A2",
        ingested_at=datetime(2026, 2, 1, 0, 0, 0, tzinfo=timezone.utc),
    )

    # Repository returns only old_asset (filtered by computed_at)
    use_case = _make_use_case(
        report=_report(audit_hash=_HASH),
        assets_at_time=[old_asset],
    )
    with patch(
        "app.application.use_cases.verify_report.compute_asset_hash",
        return_value=_HASH,
    ) as mock_hash:
        result = use_case.execute("facility-a", _REPORT_ID)

    assert result.is_valid is True
    called_assets = mock_hash.call_args[0][1]
    assert new_asset not in called_assets
    assert old_asset in called_assets


def test_state_passed_to_hash_uses_report_sealed_values() -> None:
    """The FacilityCovenantState fed to compute_asset_hash must use the
    accumulated_numerator/denominator stored in the report, not recomputed
    from asset contributions (which have Numeric(30,10) truncation in the DB)."""
    use_case = _make_use_case(
        report=_report(
            audit_hash=_HASH,
            accumulated_numerator=Decimal("190000"),
            accumulated_denominator=Decimal("10000"),
        ),
        assets_at_time=[_asset()],
    )
    with patch(
        "app.application.use_cases.verify_report.compute_asset_hash",
        return_value=_HASH,
    ) as mock_hash:
        use_case.execute("facility-a", _REPORT_ID)

    state_arg = mock_hash.call_args[0][2]
    assert state_arg.effective_rate == Decimal("19.00")
    assert state_arg.accumulated_numerator == Decimal("190000")
    assert state_arg.accumulated_denominator == Decimal("10000")
