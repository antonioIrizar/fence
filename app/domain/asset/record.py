from datetime import datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from app.domain.asset.base import BaseAsset


class AssetRecord(BaseAsset):
    """
    Persisted record of a raw asset ingested for a facility.

    Inherits `external_id`, `amount`, `is_eligible` from BaseAsset (originator flags).

    Additional fields:
    - `is_eligible_asset`: our eligibility verdict (facility-specific rules).
    - `exclusion_reasons`: why the asset was excluded (empty if eligible).
    - `contribution_numerator` / `contribution_denominator`: per-asset weighted
      components stored to enable future UPDATE lifecycle (delta computation).
    - `raw`: full original payload for auditability / debugging.
    """

    id: UUID
    facility_id: str
    status: str
    raw: dict[str, Any]
    ingested_at: datetime
    is_eligible_asset: bool = False
    exclusion_reasons: list[str] = []
    contribution_numerator: Optional[Decimal] = None
    contribution_denominator: Optional[Decimal] = None
