from decimal import Decimal

from pydantic import BaseModel


class BaseAsset(BaseModel):
    """Shared fields present in every facility's asset data."""

    external_id: str
    amount: Decimal
    is_eligible: bool
