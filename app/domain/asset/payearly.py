from datetime import date, datetime
from decimal import Decimal

from app.domain.asset.base import BaseAsset


class PayEarlyAsset(BaseAsset):
    """Asset model for Facility B — PayEarly US (Earned Wage Access)."""

    status: str
    outstanding_principal_amount: Decimal
    total_principal_amount: Decimal
    repaid_principal_amount: Decimal
    total_fee_amount: Decimal
    created_at: datetime
    due_date: date
    days_past_due: int
    receivable_currency: str
    employer_id: str
    employer_name: str
    employee_id: str
    user_state: str
