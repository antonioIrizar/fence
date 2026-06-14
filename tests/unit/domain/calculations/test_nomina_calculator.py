from decimal import Decimal

import pytest

from app.domain.calculations.nomina import (
    NominaCalculator,
    NominaEligibilityPolicy,
    NominaMapper,
)
from app.domain.errors import InvalidPortfolioData


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

    def test_threshold_property(self) -> None:
        assert self.calc.threshold == Decimal("5.00")

    def test_eligible_asset_computes_annualized_fee_contribution(self) -> None:
        # outstanding=900, fee=2.5%, 2024-05-31 to 31/01/2025 → 8 months
        # annualized_fee = 2.5 * (12/8) = 3.75
        # numerator = 900 * 3.75 = 3375
        # denominator = 900
        result = self.calc.process_asset(
            self._make_raw("NOM-001", "900", "2.5", "2024-05-31", "31/01/2025")
        )
        assert result.is_eligible is True
        expected = Decimal("900") * Decimal("2.5") * (Decimal("12") / Decimal("8"))
        assert result.numerator == expected
        assert result.denominator == Decimal("900")

    def test_weighted_sum_of_two_assets(self) -> None:
        # Asset1: outstanding=900, annualized=3.75  → numerator=3375, denom=900
        # Asset2: outstanding=2500, 7 months         → numerator=2500*(2*(12/7))
        r1 = self.calc.process_asset(
            self._make_raw("NOM-001", "900", "2.5", "2024-05-31", "31/01/2025")
        )
        r2 = self.calc.process_asset(
            self._make_raw("NOM-002", "2500", "2.0", "2024-06-27", "31/01/2025")
        )
        from decimal import ROUND_HALF_UP
        total_num = r1.numerator + r2.numerator
        total_den = r1.denominator + r2.denominator
        rate = (total_num / total_den).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        assert rate == Decimal("3.51")

    def test_ineligible_asset_has_no_contribution(self) -> None:
        result = self.calc.process_asset(
            self._make_raw(
                "NOM-002", "4100", "2.5", "2024-06-21", "31/08/2024",
                status="written_off", is_eligible=False,
            )
        )
        assert result.is_eligible is False
        assert result.numerator is None
        assert result.denominator is None
