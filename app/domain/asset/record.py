from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from domain.asset.base import BaseAsset


class AssetRecord(BaseAsset):
    """
    Persisted record of a raw asset ingested for a facility.

    Stores extracted scalar fields for querying plus the full raw payload
    in `raw` for auditability and debugging.
    """

    id: UUID
    facility_id: str
    status: str
    raw: dict[str, Any]
    ingested_at: datetime
