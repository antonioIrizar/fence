from decimal import Decimal

import pytest

from app.domain.calculations.payearly import (
    PayEarlyCalculator,
    PayEarlyEligibilityPolicy,
    PayEarlyMapper,
)
from app.domain.covenant.entities import CovenantStatus
from app.domain.errors import CovenantCalculationError, InvalidPortfolioData


class TestPayEarlyEligibilityPolicy:
    def setup_method(self) -> None:
        self.policy = PayEarlyEligibilityPolicy()
        self.mapper = PayEarlyMapper()

    def _base_raw(self) -> dict:
        return {
            "external_id": "PE-001",
            "status": "performing",
            "is_eligible": True,
            "outstanding_principal_amount": 3400.0,
            "total_principal_amount": 8500.0,
            "repaid_principal_amount": 5100.0,
            "total_fee_amount": 1.75,
            "outstanding_fee_amount": 1.75,
            "created_at": "2025-06-15T09:00:00+00:00",
            "due_date": "2026-03-15",
            "days_past_due": 0,
            "receivable_currency": "USD",
            "employer_id": "EMP-001",
            "employer_name": "ACME Corp",
            "employee_id": "EE-001",
            "user_state": "WI",
            "amount": 8500.0,
        }

    def test_eligible_asset(self) -> None:
        asset = self.mapper.map(self._base_raw())
        ok, reasons = self.policy.check(asset)
        assert ok is True
        assert reasons == []

    def test_status_case_insensitive(self) -> None:
        for status in ("performing", "PERFORMING", "Performing"):
            raw = {**self._base_raw(), "status": status}
            asset = self.mapper.map(raw)
            ok, _ = self.policy.check(asset)
            assert ok is True, f"Expected eligible for status={status!r}"

    def test_ineligible_wrong_status(self) -> None:
        raw = {**self._base_raw(), "status": "defaulted"}
        asset = self.mapper.map(raw)
        ok, reasons = self.policy.check(asset)
        assert ok is False
        assert any("status" in r for r in reasons)

    def test_ineligible_is_eligible_false(self) -> None:
        raw = {**self._base_raw(), "is_eligible": False}
        asset = self.mapper.map(raw)
        ok, reasons = self.policy.check(asset)
        assert ok is False
        assert any("is_eligible" in r for r in reasons)

    def test_ineligible_zero_outstanding_principal(self) -> None:
        raw = {**self._base_raw(), "outstanding_principal_amount": 0.0}
        asset = self.mapper.map(raw)
        ok, reasons = self.policy.check(asset)
        assert ok is False
        assert any("outstanding_principal_amount" in r for r in reasons)


class TestPayEarlyMapper:
    def setup_method(self) -> None:
        self.mapper = PayEarlyMapper()

    def _valid_raw(self) -> dict:
        return {
            "external_id": "PE-001",
            "status": "performing",
            "is_eligible": True,
            "outstanding_principal_amount": 3400.0,
            "total_principal_amount": 8500.0,
            "repaid_principal_amount": 5100.0,
            "total_fee_amount": 1.75,
            "outstanding_fee_amount": 1.75,
            "created_at": "2025-06-15T09:00:00+00:00",
            "due_date": "2026-03-15",
            "days_past_due": 0,
            "receivable_currency": "USD",
            "employer_id": "EMP-001",
            "employer_name": "ACME Corp",
            "employee_id": "EE-001",
            "user_state": "WI",
            "amount": 8500.0,
        }

    def test_maps_valid_raw(self) -> None:
        asset = self.mapper.map(self._valid_raw())
        assert asset.external_id == "PE-001"
        assert asset.outstanding_principal_amount == Decimal("3400.0")
        assert asset.total_fee_amount == Decimal("1.75")

    def test_raises_on_missing_field(self) -> None:
        raw = self._valid_raw()
        del raw["total_principal_amount"]
        with pytest.raises(InvalidPortfolioData):
            self.mapper.map(raw)


class TestPayEarlyCalculator:
    def setup_method(self) -> None:
        self.calc = PayEarlyCalculator()

    def _make_raw(
        self,
        external_id: str,
        outstanding_principal: str,
        total_principal: str,
        total_fee: str,
        created_at: str,
        due_date: str,
        status: str = "performing",
        is_eligible: bool = True,
    ) -> dict:
        return {
            "external_id": external_id,
            "status": status,
            "is_eligible": is_eligible,
            "outstanding_principal_amount": float(outstanding_principal),
            "total_principal_amount": float(total_principal),
            "repaid_principal_amount": 0.0,
            "total_fee_amount": float(total_fee),
            "outstanding_fee_amount": float(total_fee),
            "created_at": created_at,
            "due_date": due_date,
            "days_past_due": 0,
            "receivable_currency": "USD",
            "employer_id": "EMP-001",
            "employer_name": "ACME Corp",
            "employee_id": "EE-001",
            "user_state": "WI",
            "amount": float(total_principal),
        }

    def test_fee_yield_calculation(self) -> None:
        # Asset: total_principal=8500, fee=1.75, created=2025-06-15, due=2026-03-15
        # tenor_days = 273 days
        # fee_yield = (1.75/8500) * (365/273) = 0.00020588 * 1.33699 ≈ 0.00027531
        # fee_yield_pct = 0.027531% → rounds to 0.03%
        raw_assets = [
            self._make_raw(
                "PE-001",
                "3400",
                "8500",
                "1.75",
                "2025-06-15T09:00:00+00:00",
                "2026-03-15",
            )
        ]
        report = self.calc.calculate(raw_assets, "facility-b", "corr-001")
        assert report.effective_rate == Decimal("0.03")
        assert report.status == CovenantStatus.COMPLIANT

    def test_compliant_below_threshold(self) -> None:
        raw_assets = [
            self._make_raw(
                "PE-001",
                "1000",
                "1000",
                "5.0",
                "2024-01-01T00:00:00+00:00",
                "2024-12-31",
            )
        ]
        # fee_yield = (5/1000)*(365/365) = 0.005 = 0.5% — compliant
        report = self.calc.calculate(raw_assets, "facility-b", "corr-001")
        assert report.status == CovenantStatus.COMPLIANT

    def test_breach_above_threshold(self) -> None:
        # fee_yield = (100/1000)*(365/365) = 10% > 3%
        raw_assets = [
            self._make_raw(
                "PE-001",
                "1000",
                "1000",
                "100.0",
                "2024-01-01T00:00:00+00:00",
                "2024-12-31",
            )
        ]
        report = self.calc.calculate(raw_assets, "facility-b", "corr-001")
        assert report.status == CovenantStatus.BREACH

    def test_excluded_defaulted_asset(self) -> None:
        raw_assets = [
            self._make_raw(
                "PE-001",
                "3400",
                "8500",
                "1.75",
                "2025-06-15T09:00:00+00:00",
                "2026-03-15",
            ),
            self._make_raw(
                "PE-002",
                "7111",
                "7111",
                "2.92",
                "2023-07-22T13:52:25+00:00",
                "2025-07-28",
                status="defaulted",
            ),
        ]
        report = self.calc.calculate(raw_assets, "facility-b", "corr-001")
        assert "PE-001" in report.included_assets
        assert "PE-002" in [e.external_id for e in report.excluded_assets]

    def test_raises_when_no_eligible_assets(self) -> None:
        raw_assets = [
            self._make_raw(
                "PE-001",
                "7111",
                "7111",
                "2.92",
                "2023-07-22T13:52:25+00:00",
                "2025-07-28",
                status="defaulted",
            )
        ]
        with pytest.raises(CovenantCalculationError):
            self.calc.calculate(raw_assets, "facility-b", "corr-001")

    def test_threshold_stored_in_report(self) -> None:
        raw_assets = [
            self._make_raw(
                "PE-001",
                "3400",
                "8500",
                "1.75",
                "2025-06-15T09:00:00+00:00",
                "2026-03-15",
            )
        ]
        report = self.calc.calculate(raw_assets, "facility-b", "corr-001")
        assert report.threshold == Decimal("3.00")
