"""Tests for defensive branches to achieve 100% coverage on calculations."""

import pytest

from app.domain.asset.base import BaseAsset
from app.domain.calculations.educa import EducaEligibilityPolicy, EducaMapper
from app.domain.calculations.nomina import NominaEligibilityPolicy, NominaMapper
from app.domain.calculations.payearly import PayEarlyEligibilityPolicy, PayEarlyMapper
from app.domain.errors import InvalidPortfolioData
from decimal import Decimal


class _WrongAsset(BaseAsset):
    pass


_WRONG = _WrongAsset(external_id="X", amount=Decimal("0"), is_eligible=True)


class TestEligibilityPolicyWrongAssetType:
    def test_educa_policy_rejects_wrong_type(self) -> None:
        ok, reasons = EducaEligibilityPolicy().check(_WRONG)
        assert ok is False
        assert "EducaAsset" in reasons[0]

    def test_payearly_policy_rejects_wrong_type(self) -> None:
        ok, reasons = PayEarlyEligibilityPolicy().check(_WRONG)
        assert ok is False
        assert "PayEarlyAsset" in reasons[0]

    def test_nomina_policy_rejects_wrong_type(self) -> None:
        ok, reasons = NominaEligibilityPolicy().check(_WRONG)
        assert ok is False
        assert "NominaAsset" in reasons[0]


class TestNominaRepaymentMonthsGuard:
    """Tests the min-1-month guard in _repayment_months."""

    def test_same_month_gives_minimum_one(self) -> None:
        """origination and maturity in same calendar month → 1 month floor."""
        from app.domain.calculations.nomina import NominaCalculator

        calc = NominaCalculator()
        raw = {
            "external_id": "NOM-FLOOR",
            "status": "active",
            "is_eligible": True,
            "outstanding_amount": 1000.0,
            "fee_percentage": 2.0,
            "fee_amount": 20.0,
            "origination_date": "2024-06-15",
            "maturity_date": "30/06/2024",  # same month
            "net_monthly_salary": 3000.0,
            "advance_amount": 1000.0,
            "repaid_amount": 0.0,
            "days_past_due": 0,
            "employer_name": "ACME",
            "employer_tax_id": "ESA123",
            "amount": 1000.0,
        }
        report = calc.calculate([raw], "facility-c", "corr-floor")
        # annualized_fee = 2.0 * (12/1) = 24.0
        from decimal import Decimal

        assert report.effective_rate == Decimal("24.00")


class TestMapperGeneralException:
    def test_educa_mapper_raises_on_malformed_date(self) -> None:
        raw = {
            "external_id": "X",
            "amount": 1000.0,
            "is_eligible": True,
            "status": "open",
            "loan_status": "current",
            "interest_rate_percentage": 20.0,
            "outstanding_amount": 1000.0,
            "disbursement_amount": 1000.0,
            "repaid_amount": 0.0,
            "effective_date": "not-a-date",
            "reporting_date": "2026-01-15",
            "student_id": "STU-001",
            "school_id": "SCH-001",
            "days_past_due": 0,
            "country": "ES",
        }
        with pytest.raises(InvalidPortfolioData):
            EducaMapper().map(raw)

    def test_payearly_mapper_raises_on_malformed_date(self) -> None:
        raw = {
            "external_id": "X",
            "amount": 1000.0,
            "is_eligible": True,
            "status": "performing",
            "outstanding_principal_amount": 500.0,
            "total_principal_amount": 1000.0,
            "repaid_principal_amount": 500.0,
            "total_fee_amount": 1.0,
            "outstanding_fee_amount": 1.0,
            "created_at": "not-a-datetime",
            "due_date": "2026-03-15",
            "days_past_due": 0,
            "receivable_currency": "USD",
            "employer_id": "EMP",
            "employer_name": "ACME",
            "employee_id": "EE",
            "user_state": "CA",
        }
        with pytest.raises(InvalidPortfolioData):
            PayEarlyMapper().map(raw)

    def test_nomina_mapper_raises_on_invalid_fee(self) -> None:
        raw = {
            "external_id": "X",
            "amount": 1000.0,
            "is_eligible": True,
            "status": "active",
            "outstanding_amount": 500.0,
            "fee_percentage": "not-a-number",
            "fee_amount": 25.0,
            "origination_date": "2024-05-31",
            "maturity_date": "31/01/2025",
            "net_monthly_salary": 3000.0,
            "advance_amount": 1000.0,
            "repaid_amount": 500.0,
            "days_past_due": 0,
            "employer_name": "ACME",
            "employer_tax_id": "ESA123",
        }
        with pytest.raises(InvalidPortfolioData):
            NominaMapper().map(raw)
