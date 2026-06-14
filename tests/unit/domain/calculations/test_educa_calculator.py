from decimal import Decimal

import pytest

from app.domain.calculations.educa import (
    EducaCalculator,
    EducaEligibilityPolicy,
    EducaMapper,
)
from app.domain.errors import InvalidPortfolioData

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

    def test_threshold_property(self) -> None:
        assert self.calc.threshold == Decimal("22.00")

    def test_eligible_asset_computes_weighted_contribution(self) -> None:
        # numerator = outstanding * rate = 4875 * 20.86
        # denominator = outstanding = 4875
        result = self.calc.process_asset(self._make_raw("A1", "4875", "20.86"))
        assert result.is_eligible is True
        assert result.numerator == Decimal("4875") * Decimal("20.86")
        assert result.denominator == Decimal("4875")

    def test_ineligible_asset_has_no_contribution(self) -> None:
        result = self.calc.process_asset(
            self._make_raw("A2", "7100", "25.11", loan_status="delinquent")
        )
        assert result.is_eligible is False
        assert result.numerator is None
        assert result.denominator is None

    def test_null_rate_asset_is_ineligible(self) -> None:
        raw = {**self._make_raw("A2", "7000", "0"), "interest_rate_percentage": None}
        result = self.calc.process_asset(raw)
        assert result.is_eligible is False
        assert result.numerator is None
