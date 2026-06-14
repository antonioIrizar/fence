"""Tests for FacilityCalculator.process_asset() and .threshold on each calculator."""

from decimal import Decimal
from typing import Any

import pytest

from app.domain.calculations.educa import EducaCalculator
from app.domain.calculations.nomina import NominaCalculator
from app.domain.calculations.payearly import PayEarlyCalculator
from app.domain.errors import InvalidPortfolioData


def _educa_raw(
    external_id: str = "EDU-001",
    status: str = "open",
    loan_status: str = "current",
    rate: str | None = "20.0",
    is_eligible: bool = True,
) -> dict[str, Any]:
    return {
        "external_id": external_id,
        "amount": "10000",
        "is_eligible": is_eligible,
        "status": status,
        "loan_status": loan_status,
        "outstanding_amount": "9500",
        "interest_rate_percentage": rate,
        "effective_date": "2024-01-01",
        "reporting_date": "2024-06-01",
        "student_id": "STU-001",
        "school_id": "SCH-001",
        "disbursement_amount": "10000",
        "repaid_amount": "500",
        "days_past_due": 0,
        "country": "ES",
    }


def _payearly_raw(
    external_id: str = "PE-001",
    status: str = "performing",
    outstanding: str = "4500",
    is_eligible: bool = True,
) -> dict[str, Any]:
    return {
        "external_id": external_id,
        "amount": "5000",
        "is_eligible": is_eligible,
        "status": status,
        "outstanding_principal_amount": outstanding,
        "total_principal_amount": "5000",
        "repaid_principal_amount": "500",
        "total_fee_amount": "50",
        "outstanding_fee_amount": "45",
        "created_at": "2024-01-01T00:00:00",
        "due_date": "2024-02-01",
        "days_past_due": 0,
        "receivable_currency": "USD",
        "employer_id": "EMP-001",
        "employer_name": "Acme Corp",
        "employee_id": "EMP001",
        "user_state": "active",
    }


def _nomina_raw(
    external_id: str = "NOM-001",
    status: str = "active",
    outstanding: str = "2800",
    is_eligible: bool = True,
) -> dict[str, Any]:
    return {
        "external_id": external_id,
        "amount": "3000",
        "is_eligible": is_eligible,
        "status": status,
        "outstanding_amount": outstanding,
        "fee_percentage": "2",
        "fee_amount": "60",
        "origination_date": "2024-01-01",
        "maturity_date": "01/07/2024",
        "net_monthly_salary": "3000",
        "advance_amount": "3000",
        "repaid_amount": "200",
        "days_past_due": 0,
        "employer_name": "Empresa SA",
        "employer_tax_id": "TAX-001",
    }


# ── Educa (facility-a) ────────────────────────────────────────────────────────


class TestEducaProcessAsset:
    def setup_method(self) -> None:
        self.calc = EducaCalculator()

    def test_threshold(self) -> None:
        assert self.calc.threshold == Decimal("22.00")

    def test_eligible_asset_returns_contributions(self) -> None:
        result = self.calc.process_asset(_educa_raw())
        assert result.is_eligible is True
        assert result.exclusion_reasons == []
        # numerator = 9500 * 20 = 190_000
        assert result.numerator == Decimal("190000.0")
        # denominator = outstanding_amount
        assert result.denominator == Decimal("9500")

    def test_ineligible_status_returns_no_contributions(self) -> None:
        result = self.calc.process_asset(_educa_raw(status="closed"))
        assert result.is_eligible is False
        assert result.numerator is None
        assert result.denominator is None
        assert any("status" in r for r in result.exclusion_reasons)

    def test_ineligible_rate_none_returns_no_contributions(self) -> None:
        result = self.calc.process_asset(_educa_raw(rate=None))
        assert result.is_eligible is False
        assert result.numerator is None

    def test_malformed_raw_raises(self) -> None:
        with pytest.raises(InvalidPortfolioData):
            self.calc.process_asset({"external_id": "X"})  # missing required fields


# ── PayEarly (facility-b) ──────────────────────────────────────────────────────


class TestPayEarlyProcessAsset:
    def setup_method(self) -> None:
        self.calc = PayEarlyCalculator()

    def test_threshold(self) -> None:
        assert self.calc.threshold == Decimal("3.00")

    def test_eligible_asset_returns_contributions(self) -> None:
        result = self.calc.process_asset(_payearly_raw())
        assert result.is_eligible is True
        assert result.exclusion_reasons == []
        # tenor_days = 31 (Jan 1 → Feb 1)
        # fee_yield = (50/5000) * (365/31) = 0.01 * 11.774... = 0.1177...
        # fee_yield_pct = 11.774...
        # numerator = 4500 * fee_yield_pct
        assert result.numerator is not None
        assert result.denominator == Decimal("4500")
        # sanity: numerator > 0
        assert result.numerator > Decimal("0")

    def test_ineligible_status_returns_no_contributions(self) -> None:
        result = self.calc.process_asset(_payearly_raw(status="defaulted"))
        assert result.is_eligible is False
        assert result.numerator is None

    def test_zero_outstanding_ineligible(self) -> None:
        result = self.calc.process_asset(_payearly_raw(outstanding="0"))
        assert result.is_eligible is False

    def test_malformed_raw_raises(self) -> None:
        with pytest.raises(InvalidPortfolioData):
            self.calc.process_asset({"external_id": "X"})


# ── Nomina (facility-c) ───────────────────────────────────────────────────────


class TestNominaProcessAsset:
    def setup_method(self) -> None:
        self.calc = NominaCalculator()

    def test_threshold(self) -> None:
        assert self.calc.threshold == Decimal("5.00")

    def test_eligible_asset_returns_contributions(self) -> None:
        result = self.calc.process_asset(_nomina_raw())
        assert result.is_eligible is True
        assert result.exclusion_reasons == []
        # maturity 01/07/2024, origination 2024-01-01 → 6 months
        # annualized_fee = 2 * (12/6) = 4
        # numerator = 2800 * 4 = 11200
        assert result.numerator == Decimal("11200")
        assert result.denominator == Decimal("2800")

    def test_ineligible_status_returns_no_contributions(self) -> None:
        result = self.calc.process_asset(_nomina_raw(status="past_due"))
        assert result.is_eligible is False
        assert result.numerator is None

    def test_malformed_raw_raises(self) -> None:
        with pytest.raises(InvalidPortfolioData):
            self.calc.process_asset({"external_id": "X"})
