from decimal import Decimal

import pytest

from app.domain.calculations.educa import (
    EducaCalculator,
    EducaEligibilityPolicy,
    EducaMapper,
)
from app.domain.covenant.entities import CovenantStatus
from app.domain.errors import CovenantCalculationError, InvalidPortfolioData

# ---------------------------------------------------------------------------
# EducaEligibilityPolicy
# ---------------------------------------------------------------------------


class TestEducaEligibilityPolicy:
    def setup_method(self) -> None:
        self.policy = EducaEligibilityPolicy()

    def _base_raw(self) -> dict:
        return {
            "external_id": "EDU-001",
            "status": "open",
            "is_eligible": True,
            "loan_status": "current",
            "interest_rate_percentage": 20.0,
            "outstanding_amount": 5000.0,
            "disbursement_amount": 5000.0,
            "repaid_amount": 0.0,
            "effective_date": "2024-01-01",
            "reporting_date": "2026-01-15",
            "student_id": "STU-001",
            "school_id": "SCH-001",
            "days_past_due": 0,
            "country": "ES",
            "amount": 5000.0,
        }

    def test_eligible_asset(self) -> None:
        asset = EducaMapper().map(self._base_raw())
        ok, reasons = self.policy.check(asset)
        assert ok is True
        assert reasons == []

    def test_status_case_insensitive(self) -> None:
        for status in ("open", "Open", "OPEN"):
            raw = {**self._base_raw(), "status": status}
            asset = EducaMapper().map(raw)
            ok, _ = self.policy.check(asset)
            assert ok is True, f"Expected eligible for status={status!r}"

    def test_ineligible_wrong_status(self) -> None:
        raw = {**self._base_raw(), "status": "closed"}
        asset = EducaMapper().map(raw)
        ok, reasons = self.policy.check(asset)
        assert ok is False
        assert any("status" in r for r in reasons)

    def test_ineligible_is_eligible_false(self) -> None:
        raw = {**self._base_raw(), "is_eligible": False}
        asset = EducaMapper().map(raw)
        ok, reasons = self.policy.check(asset)
        assert ok is False
        assert any("is_eligible" in r for r in reasons)

    def test_ineligible_wrong_loan_status(self) -> None:
        raw = {**self._base_raw(), "loan_status": "delinquent"}
        asset = EducaMapper().map(raw)
        ok, reasons = self.policy.check(asset)
        assert ok is False
        assert any("loan_status" in r for r in reasons)

    def test_ineligible_null_interest_rate(self) -> None:
        raw = {**self._base_raw(), "interest_rate_percentage": None}
        asset = EducaMapper().map(raw)
        ok, reasons = self.policy.check(asset)
        assert ok is False
        assert any("interest_rate_percentage" in r for r in reasons)

    def test_multiple_failures_reported(self) -> None:
        raw = {
            **self._base_raw(),
            "status": "closed",
            "is_eligible": False,
        }
        asset = EducaMapper().map(raw)
        ok, reasons = self.policy.check(asset)
        assert ok is False
        assert len(reasons) >= 2


# ---------------------------------------------------------------------------
# EducaMapper
# ---------------------------------------------------------------------------


class TestEducaMapper:
    def setup_method(self) -> None:
        self.mapper = EducaMapper()

    def _valid_raw(self) -> dict:
        return {
            "external_id": "EDU-001",
            "status": "open",
            "is_eligible": True,
            "loan_status": "current",
            "interest_rate_percentage": 20.86,
            "outstanding_amount": 4875.0,
            "disbursement_amount": 6500.0,
            "repaid_amount": 1625.0,
            "effective_date": "2024-06-25",
            "reporting_date": "2026-01-15",
            "student_id": "STU-10001",
            "school_id": "SCH-001",
            "days_past_due": 0,
            "country": "ES",
            "amount": 6500.0,
        }

    def test_maps_valid_raw(self) -> None:
        asset = self.mapper.map(self._valid_raw())
        assert asset.external_id == "EDU-001"
        assert asset.outstanding_amount == Decimal("4875.0")
        assert asset.interest_rate_percentage == Decimal("20.86")
        assert asset.is_eligible is True

    def test_maps_null_interest_rate(self) -> None:
        raw = {**self._valid_raw(), "interest_rate_percentage": None}
        asset = self.mapper.map(raw)
        assert asset.interest_rate_percentage is None

    def test_raises_on_missing_external_id(self) -> None:
        raw = self._valid_raw()
        del raw["external_id"]
        with pytest.raises(InvalidPortfolioData):
            self.mapper.map(raw)

    def test_raises_on_missing_outstanding_amount(self) -> None:
        raw = self._valid_raw()
        del raw["outstanding_amount"]
        with pytest.raises(InvalidPortfolioData):
            self.mapper.map(raw)


# ---------------------------------------------------------------------------
# EducaCalculator
# ---------------------------------------------------------------------------


class TestEducaCalculator:
    def setup_method(self) -> None:
        self.calc = EducaCalculator()

    def _make_raw(
        self,
        external_id: str,
        outstanding: str,
        rate: str,
        status: str = "open",
        loan_status: str = "current",
        is_eligible: bool = True,
    ) -> dict:
        return {
            "external_id": external_id,
            "status": status,
            "is_eligible": is_eligible,
            "loan_status": loan_status,
            "interest_rate_percentage": float(rate),
            "outstanding_amount": float(outstanding),
            "disbursement_amount": float(outstanding),
            "repaid_amount": 0.0,
            "effective_date": "2024-01-01",
            "reporting_date": "2026-01-15",
            "student_id": "STU-001",
            "school_id": "SCH-001",
            "days_past_due": 0,
            "country": "ES",
            "amount": float(outstanding),
        }

    def test_weighted_average_calculation(self) -> None:
        # Two assets: outstanding 4875 @ 20.86%, 10200 @ 18.54%
        # Weighted sum = 4875*20.86 + 10200*18.54 = 101694.5 + 189108 = 290802.5
        # Total outstanding = 15075
        # Rate = 290802.5 / 15075 ≈ 19.29%
        raw_assets = [
            self._make_raw("A1", "4875", "20.86"),
            self._make_raw("A2", "10200", "18.54"),
        ]
        report = self.calc.calculate(raw_assets, "facility-a", "corr-001")
        assert report.effective_rate == Decimal("19.29")

    def test_excluded_assets_in_report(self) -> None:
        raw_assets = [
            self._make_raw("A1", "4875", "20.86"),
            self._make_raw("A2", "7100", "25.11", loan_status="delinquent"),
            self._make_raw("A3", "3200", "19.50", status="closed"),
        ]
        report = self.calc.calculate(raw_assets, "facility-a", "corr-001")
        assert "A1" in report.included_assets
        excluded_ids = [e.external_id for e in report.excluded_assets]
        assert "A2" in excluded_ids
        assert "A3" in excluded_ids

    def test_summary_counts(self) -> None:
        raw_assets = [
            self._make_raw("A1", "4875", "20.86"),
            self._make_raw("A2", "7100", "25.11", loan_status="delinquent"),
        ]
        report = self.calc.calculate(raw_assets, "facility-a", "corr-001")
        assert report.total_assets == 2
        assert len(report.included_assets) == 1
        assert len(report.excluded_assets) == 1

    def test_compliant_status_below_threshold(self) -> None:
        raw_assets = [self._make_raw("A1", "10000", "20.00")]
        report = self.calc.calculate(raw_assets, "facility-a", "corr-001")
        assert report.status == CovenantStatus.COMPLIANT

    def test_breach_status_at_threshold(self) -> None:
        raw_assets = [self._make_raw("A1", "10000", "22.00")]
        report = self.calc.calculate(raw_assets, "facility-a", "corr-001")
        assert report.status == CovenantStatus.BREACH

    def test_breach_status_above_threshold(self) -> None:
        raw_assets = [self._make_raw("A1", "10000", "25.00")]
        report = self.calc.calculate(raw_assets, "facility-a", "corr-001")
        assert report.status == CovenantStatus.BREACH

    def test_raises_when_no_eligible_assets(self) -> None:
        raw_assets = [
            self._make_raw("A1", "7100", "25.11", loan_status="delinquent"),
        ]
        with pytest.raises(CovenantCalculationError):
            self.calc.calculate(raw_assets, "facility-a", "corr-001")

    def test_threshold_stored_in_report(self) -> None:
        raw_assets = [self._make_raw("A1", "10000", "20.00")]
        report = self.calc.calculate(raw_assets, "facility-a", "corr-001")
        assert report.threshold == Decimal("22.00")

    def test_null_rate_excluded(self) -> None:
        raw_assets = [
            self._make_raw("A1", "4875", "20.86"),
            {
                **self._make_raw("A2", "7000", "0"),
                "interest_rate_percentage": None,
            },
        ]
        report = self.calc.calculate(raw_assets, "facility-a", "corr-001")
        assert "A2" in [e.external_id for e in report.excluded_assets]
        assert "A1" in report.included_assets
