from datetime import date
from decimal import Decimal
from typing import Optional

from app.domain.asset.base import BaseAsset


class EducaAsset(BaseAsset):
    """Asset model for Facility A — Educa Capital I (ISA / Education Loans)."""

    status: str
    loan_status: str
    outstanding_amount: Decimal
    interest_rate_percentage: Optional[Decimal]
    effective_date: date
    reporting_date: date
    student_id: str
    school_id: str
    disbursement_amount: Decimal
    repaid_amount: Decimal
    days_past_due: int
    country: str
