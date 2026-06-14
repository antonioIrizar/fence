from decimal import Decimal
from typing import Optional

from pydantic import BaseModel

from app.domain.asset.base import BaseAsset


class AssetProcessingResult(BaseModel):
    """
    Result of running a single raw asset through the facility pipeline.

    Carries the mapped domain asset, eligibility verdict, and — for eligible
    assets — the pre-computed weighted-average components (numerator /
    denominator) that can be accumulated incrementally into the facility's
    covenant state.

    Ineligible assets have numerator = denominator = None.
    """

    asset: BaseAsset
    is_eligible: bool
    exclusion_reasons: list[str]
    numerator: Optional[Decimal]
    denominator: Optional[Decimal]
