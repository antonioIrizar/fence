from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel


class CovenantStatus(str, Enum):
    COMPLIANT = "COMPLIANT"
    BREACH = "BREACH"


class ExcludedAsset(BaseModel):
    external_id: str
    reasons: list[str]


class CovenantReport(BaseModel):
    """
    Immutable record of a covenant calculation result for one facility.

    Inputs: raw portfolio data from the originator.
    Outputs: effective_rate (%), covenant status, asset breakdown.
    """

    report_id: UUID
    facility_id: str
    effective_rate: Decimal
    threshold: Decimal
    status: CovenantStatus
    total_assets: int
    included_assets: list[str]
    excluded_assets: list[ExcludedAsset]
    computed_at: datetime
    correlation_id: str
    audit_hash: str
    accumulated_numerator: Decimal
    accumulated_denominator: Decimal
