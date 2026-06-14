from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.application.queries.get_report import GetCovenantReportQuery
from app.application.use_cases.get_covenant_report import GetCovenantReportUseCase
from app.domain.covenant.entities import CovenantReport, CovenantStatus
from app.domain.errors import CovenantCalculationError

_REPORT_ID = uuid4()
_COMPUTED_AT = datetime(2026, 1, 10, 12, 0, 0, tzinfo=timezone.utc)
_HASH = "a" * 64


def _report(facility_id: str = "facility-a") -> CovenantReport:
    return CovenantReport(
        report_id=_REPORT_ID,
        facility_id=facility_id,
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


def _make_use_case(report: CovenantReport | None) -> GetCovenantReportUseCase:
    repo = MagicMock()
    repo.find_by_id.return_value = report
    return GetCovenantReportUseCase(repository=repo)


def _query(facility_id: str = "facility-a") -> GetCovenantReportQuery:
    return GetCovenantReportQuery(facility_id=facility_id, report_id=_REPORT_ID)


def test_raises_when_report_not_found() -> None:
    use_case = _make_use_case(report=None)
    with pytest.raises(CovenantCalculationError, match="not found"):
        use_case.execute(_query())


def test_raises_when_report_belongs_to_different_facility() -> None:
    """IDOR guard: a report from facility-b must not be readable via facility-a."""
    use_case = _make_use_case(report=_report(facility_id="facility-b"))
    with pytest.raises(CovenantCalculationError, match="does not belong"):
        use_case.execute(_query(facility_id="facility-a"))


def test_returns_report_when_facility_matches() -> None:
    report = _report(facility_id="facility-a")
    use_case = _make_use_case(report=report)
    result = use_case.execute(_query(facility_id="facility-a"))
    assert result is report
