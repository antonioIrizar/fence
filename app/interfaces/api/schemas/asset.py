from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel

from app.interfaces.api.schemas.response import (
    ExcludedAssetResponse as ExcludedAssetResponse,
)


class IngestAssetsRequest(BaseModel):
    assets: list[dict[str, Any]]


class CovenantStateResponse(BaseModel):
    facility_id: str
    accumulated_numerator: str
    accumulated_denominator: str
    effective_rate: str
    covenant_status: str
    last_updated: datetime

    @classmethod
    def from_domain(cls, state: Any) -> "CovenantStateResponse":
        return cls(
            facility_id=state.facility_id,
            accumulated_numerator=str(
                Decimal(str(state.accumulated_numerator)).quantize(Decimal("0.01"))
            ),
            accumulated_denominator=str(
                Decimal(str(state.accumulated_denominator)).quantize(Decimal("0.01"))
            ),
            effective_rate=str(
                Decimal(str(state.effective_rate)).quantize(Decimal("0.01"))
            ),
            covenant_status=state.covenant_status.value,
            last_updated=state.last_updated,
        )


class IngestAssetsResponse(BaseModel):
    saved: list[str]
    duplicates: list[str]
    saved_count: int
    duplicate_count: int
    covenant_state: CovenantStateResponse


class FacilityStateSummary(BaseModel):
    total: int
    included: int
    excluded: int


class FacilityStateResponse(BaseModel):
    covenant_state: CovenantStateResponse
    summary: FacilityStateSummary
    included_assets: list[str]
    excluded_assets: list[ExcludedAssetResponse]
