from decimal import Decimal

import pytest

from app.domain.calculations.nomina import (
    NominaCalculator,
    NominaEligibilityPolicy,
    NominaMapper,
)
from app.domain.covenant.entities import CovenantStatus
from app.domain.errors import CovenantCalculationError, InvalidPortfolioData


class TestNominaEligibilityPolicy:
    def setup_method(self) -> None:
        self.policy = NominaEligibilityPolicy()
        self.mapper = NominaMapper()

    def _base_raw(self) -> dict:
        return {
            "external_id": "NOM-001",
            "status": "active",
            "is_eligible": True,
            "outstanding_amount": 900.0,
            "fee_percentage": 2.5,
            "fee_amount": 45.0,
            "origination_date": "2024-05-31",
            "maturity_date": "31/01/2025",
            "net_monthly_salary": 3200.0,
            "advance_amount": 1800.0,
            "repaid_amount": 900.0,
            "days_past_due": 0,
            "employer_name": "Merlin Properties SOCIMI",
            "employer_tax_id": "ESA86648867",
            "amount": 1800.0,
        }

    def test_eligible_asset(self) -> None:
        asset = self.mapper.map(self._base_raw())
        ok, reasons = self.policy.check(asset)
        assert ok is True
        assert reasons == []

    def test_status_case_insensitive(self) -> None:
        for status in ("active", "ACTIVE", "Active"):
            raw = {**self._base_raw(), "status": status}
            asset = self.mapper.map(raw)
            ok, _ = self.policy.check(asset)
            assert ok is True, f"Expected eligible for status={status!r}"

    def test_ineligible_wrong_status(self) -> None:
        raw = {**self._base_raw(), "status": "written_off"}
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

    def test_ineligible_zero_outstanding(self) -> None:
        raw = {**self._base_raw(), "outstanding_amount": 0.0}
        asset = self.mapper.map(raw)
        ok, reasons = self.policy.check(asset)
        assert ok is False
        assert any("outstanding_amount" in r for r in reasons)


class TestNominaMapper:
    def setup_method(self) -> None:
        self.mapper = NominaMapper()

    def _valid_raw(self) -> dict:
        return {
            "external_id": "NOM-001",
            "status": "active",
            "is_eligible": True,
            "outstanding_amount": 900.0,
            "fee_percentage": 2.5,
            "fee_amount": 45.0,
            "origination_date": "2024-05-31",
            "maturity_date": "31/01/2025",
            "net_monthly_salary": 3200.0,
            "advance_amount": 1800.0,
            "repaid_amount": 900.0,
            "days_past_due": 0,
            "employer_name": "Merlin Properties SOCIMI",
            "employer_tax_id": "ESA86648867",
            "amount": 1800.0,
        }

    def test_maps_valid_raw(self) -> None:
        asset = self.mapper.map(self._valid_raw())
        assert asset.external_id == "NOM-001"
        assert asset.outstanding_amount == Decimal("900.0")
        assert asset.fee_percentage == Decimal("2.5")
        assert asset.maturity_date == "31/01/2025"

    def test_raises_on_missing_field(self) -> None:
        raw = self._valid_raw()
        del raw["fee_percentage"]
        with pytest.raises(InvalidPortfolioData):
            self.mapper.map(raw)


class TestNominaCalculator:
    def setup_method(self) -> None:
        self.calc = NominaCalculator()

    def _make_raw(
        self,
        external_id: str,
        outstanding: str,
        fee_percentage: str,
        origination_date: str,
        maturity_date: str,
        status: str = "active",
        is_eligible: bool = True,
    ) -> dict:
        return {
            "external_id": external_id,
            "status": status,
            "is_eligible": is_eligible,
            "outstanding_amount": float(outstanding),
            "fee_percentage": float(fee_percentage),
            "fee_amount": float(outstanding) * float(fee_percentage) / 100,
            "origination_date": origination_date,
            "maturity_date": maturity_date,
            "net_monthly_salary": 3200.0,
            "advance_amount": float(outstanding),
            "repaid_amount": 0.0,
            "days_past_due": 0,
            "employer_name": "ACME",
            "employer_tax_id": "ESA12345",
            "amount": float(outstanding),
        }

    def test_annualized_fee_calculation(self) -> None:
        # Asset: outstanding=900, fee=2.5%, 2024-05-31 to 31/01/2025
        # repayment_months = 8 months
        # annualized_fee = 2.5 * (12/8) = 3.75
        # Effective rate = 3.75 (single asset)
        raw_assets = [
            self._make_raw("NOM-001", "900", "2.5", "2024-05-31", "31/01/2025")
        ]
        report = self.calc.calculate(raw_assets, "facility-c", "corr-001")
        assert report.effective_rate == Decimal("3.75")
        assert report.status == CovenantStatus.COMPLIANT

    def test_weighted_average_two_assets(self) -> None:
        # Asset1: outstanding=900, fee=2.5%, 8 months → annualized=3.75
        # Asset2: outstanding=2500, fee=2.0%, 2024-06-27 to 31/01/2025
        #   repayment_months = 7 months, annualized = 2.0*(12/7) ≈ 3.4286
        # Weighted = (900*3.75 + 2500*3.4286) / 3400
        #          = (3375 + 8571.43) / 3400 ≈ 3.51
        raw_assets = [
            self._make_raw("NOM-001", "900", "2.5", "2024-05-31", "31/01/2025"),
            self._make_raw("NOM-002", "2500", "2.0", "2024-06-27", "31/01/2025"),
        ]
        report = self.calc.calculate(raw_assets, "facility-c", "corr-001")
        assert report.effective_rate == Decimal("3.51")

    def test_compliant_below_threshold(self) -> None:
        raw_assets = [
            self._make_raw("NOM-001", "900", "2.5", "2024-05-31", "31/01/2025")
        ]
        report = self.calc.calculate(raw_assets, "facility-c", "corr-001")
        assert report.status == CovenantStatus.COMPLIANT

    def test_breach_above_threshold(self) -> None:
        # fee=10%, 1 month tenure → annualized = 10*12 = 120% — well above 5%
        raw_assets = [
            self._make_raw("NOM-001", "1000", "10.0", "2024-12-31", "31/01/2025")
        ]
        report = self.calc.calculate(raw_assets, "facility-c", "corr-001")
        assert report.status == CovenantStatus.BREACH

    def test_excluded_written_off(self) -> None:
        raw_assets = [
            self._make_raw("NOM-001", "900", "2.5", "2024-05-31", "31/01/2025"),
            self._make_raw(
                "NOM-002",
                "4100",
                "2.5",
                "2024-06-21",
                "31/08/2024",
                status="written_off",
                is_eligible=False,
            ),
        ]
        report = self.calc.calculate(raw_assets, "facility-c", "corr-001")
        assert "NOM-001" in report.included_assets
        assert "NOM-002" in [e.external_id for e in report.excluded_assets]

    def test_raises_when_no_eligible_assets(self) -> None:
        raw_assets = [
            self._make_raw(
                "NOM-001",
                "4100",
                "2.5",
                "2024-06-21",
                "31/08/2024",
                status="written_off",
                is_eligible=False,
            )
        ]
        with pytest.raises(CovenantCalculationError):
            self.calc.calculate(raw_assets, "facility-c", "corr-001")

    def test_threshold_stored_in_report(self) -> None:
        raw_assets = [
            self._make_raw("NOM-001", "900", "2.5", "2024-05-31", "31/01/2025")
        ]
        report = self.calc.calculate(raw_assets, "facility-c", "corr-001")
        assert report.threshold == Decimal("5.00")
