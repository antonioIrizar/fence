from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel


class CovenantStateStatus(str, Enum):
    COMPLIANT = "COMPLIANT"
    BREACH = "BREACH"
    NO_DATA = "NO_DATA"  # no eligible assets have been processed yet


class FacilityCovenantState(BaseModel):
    """
    Pre-computed covenant state for a facility, updated incrementally on each
    asset ingestion.

    Stores the running weighted-average components so the effective rate can be
    derived in O(1) without re-reading every asset:
      effective_rate = accumulated_numerator / accumulated_denominator

    Designed to support lifecycle-aware updates:
      - INSERT: add asset contribution to (numerator, denominator).
      - Future UPDATE: add delta (new_contribution − old_contribution).
    """

    id: UUID
    facility_id: str
    accumulated_numerator: Decimal
    accumulated_denominator: Decimal
    effective_rate: Decimal
    covenant_status: CovenantStateStatus
    last_updated: datetime
