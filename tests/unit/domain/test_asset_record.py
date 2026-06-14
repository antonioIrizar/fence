from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.domain.asset.record import AssetRecord


def test_asset_record_creation() -> None:
    record = AssetRecord(
        id=uuid4(),
        facility_id="facility-a",
        external_id="EDU-10001",
        status="open",
        amount=Decimal("10000.00"),
        is_eligible=True,
        raw={"external_id": "EDU-10001", "status": "open"},
        ingested_at=datetime.now(timezone.utc),
    )
    assert record.facility_id == "facility-a"
    assert record.external_id == "EDU-10001"
    assert record.amount == Decimal("10000.00")
    assert record.is_eligible is True


def test_asset_record_amount_must_be_decimal() -> None:
    with pytest.raises(Exception):
        AssetRecord(
            id=uuid4(),
            facility_id="facility-a",
            external_id="EDU-10001",
            status="open",
            amount="not-a-decimal",  # type: ignore[arg-type]
            is_eligible=True,
            raw={},
            ingested_at=datetime.now(timezone.utc),
        )
