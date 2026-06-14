from decimal import Decimal

import pytest

from app.domain.calculations.payearly import (
    PayEarlyCalculator,
    PayEarlyEligibilityPolicy,
    PayEarlyMapper,
)
from app.domain.errors import InvalidPortfolioData


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

    def test_threshold_property(self) -> None:
        assert self.calc.threshold == Decimal("3.00")

    def test_eligible_asset_computes_fee_yield_contribution(self) -> None:
        # total_principal=8500, fee=1.75, created=2025-06-15, due=2026-03-15
        # tenor_days = 273
        # fee_yield_pct = (1.75/8500) * (365/273) * 100
        # numerator = outstanding(3400) * fee_yield_pct
        # denominator = outstanding(3400)
        # effective_rate = numerator/denominator = fee_yield_pct ≈ 0.03
        result = self.calc.process_asset(
            self._make_raw(
                "PE-001", "3400", "8500", "1.75",
                "2025-06-15T09:00:00+00:00", "2026-03-15",
            )
        )
        assert result.is_eligible is True
        assert result.denominator == Decimal("3400")
        from decimal import ROUND_HALF_UP
        effective_rate = (result.numerator / result.denominator).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        assert effective_rate == Decimal("0.03")

    def test_ineligible_asset_has_no_contribution(self) -> None:
        result = self.calc.process_asset(
            self._make_raw(
                "PE-002", "7111", "7111", "2.92",
                "2023-07-22T13:52:25+00:00", "2025-07-28", status="defaulted"
            )
        )
        assert result.is_eligible is False
        assert result.numerator is None
        assert result.denominator is None
