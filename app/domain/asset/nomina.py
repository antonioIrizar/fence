from datetime import date
from decimal import Decimal

from app.domain.asset.base import BaseAsset


class NominaAsset(BaseAsset):
    """Asset model for Facility C — Nomina Express I (Salary Advance)."""

    status: str
    outstanding_amount: Decimal
    fee_percentage: Decimal
    fee_amount: Decimal
    origination_date: date
    maturity_date: str  # DD/MM/YYYY format as provided by originator
    net_monthly_salary: Decimal
    advance_amount: Decimal
    repaid_amount: Decimal
    days_past_due: int
    employer_name: str
    employer_tax_id: str
