from decimal import Decimal
from datetime import datetime, timezone
from uuid import uuid4

from app.domain.covenant.entities import CovenantReport, CovenantStatus


def _make_report(facility_id: str = "facility-a") -> CovenantReport:
    return CovenantReport(
        report_id=uuid4(),
        facility_id=facility_id,
        effective_rate=Decimal("19.43"),
        threshold=Decimal("22.00"),
        status=CovenantStatus.COMPLIANT,
        total_assets=5,
        included_assets=["EDU-001", "EDU-002"],
        excluded_assets=[],
        computed_at=datetime.now(timezone.utc),
        correlation_id="corr-test-001",
    )


class TestPostgresCovenantReportRepository:
    def test_save_and_find_by_id(self, repository) -> None:
        report = _make_report()
        repository.save(report)

        found = repository.find_by_id(report.report_id)
        assert found is not None
        assert found.report_id == report.report_id
        assert found.facility_id == "facility-a"
        assert found.effective_rate == Decimal("19.43")
        assert found.status == CovenantStatus.COMPLIANT

    def test_find_by_id_returns_none_for_unknown(self, repository) -> None:
        result = repository.find_by_id(uuid4())
        assert result is None

    def test_find_by_facility_returns_reports(self, repository) -> None:
        r1 = _make_report("facility-x")
        r2 = _make_report("facility-x")
        repository.save(r1)
        repository.save(r2)

        results = repository.find_by_facility("facility-x")
        result_ids = {r.report_id for r in results}
        assert r1.report_id in result_ids
        assert r2.report_id in result_ids

    def test_find_by_facility_excludes_other_facilities(self, repository) -> None:
        r_a = _make_report("facility-alpha")
        r_b = _make_report("facility-beta")
        repository.save(r_a)
        repository.save(r_b)

        results = repository.find_by_facility("facility-alpha")
        for r in results:
            assert r.facility_id == "facility-alpha"

    def test_immutability_each_save_creates_new_row(self, repository) -> None:
        r1 = _make_report("facility-z")
        r2 = _make_report("facility-z")
        repository.save(r1)
        repository.save(r2)

        results = repository.find_by_facility("facility-z")
        result_ids = {r.report_id for r in results}
        assert r1.report_id in result_ids
        assert r2.report_id in result_ids
        assert len(result_ids) >= 2
