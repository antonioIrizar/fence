from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.domain.asset.record import AssetRecord
from app.infrastructure.repositories.postgres_asset_repository import (
    PostgresAssetRepository,
)


def _make_record(facility_id: str, external_id: str) -> AssetRecord:
    return AssetRecord(
        id=uuid4(),
        facility_id=facility_id,
        external_id=external_id,
        status="open",
        amount=Decimal("5000.00"),
        is_eligible=True,
        raw={"external_id": external_id, "status": "open", "amount": "5000.00"},
        ingested_at=datetime.now(timezone.utc),
    )


def test_save_batch_and_find_existing(db_session) -> None:
    repo = PostgresAssetRepository(db_session)
    records = [
        _make_record("facility-a", "EXT-001"),
        _make_record("facility-a", "EXT-002"),
    ]
    repo.save_batch(records)

    existing = repo.find_existing_external_ids(
        "facility-a", ["EXT-001", "EXT-002", "EXT-003"]
    )
    assert existing == {"EXT-001", "EXT-002"}


def test_find_existing_empty_when_none(db_session) -> None:
    repo = PostgresAssetRepository(db_session)
    existing = repo.find_existing_external_ids("facility-x", ["UNKNOWN-1"])
    assert existing == set()


def test_find_by_facility_returns_saved(db_session) -> None:
    repo = PostgresAssetRepository(db_session)
    record = _make_record("facility-b", "EXT-B-001")
    repo.save_batch([record])

    results = repo.find_by_facility("facility-b")
    assert any(r.external_id == "EXT-B-001" for r in results)


def test_unique_constraint_same_facility(db_session) -> None:
    from app.domain.errors import CovenantPublicationError

    repo = PostgresAssetRepository(db_session)
    record = _make_record("facility-a", "EXT-DUPE")
    repo.save_batch([record])

    duplicate = _make_record("facility-a", "EXT-DUPE")
    with pytest.raises(CovenantPublicationError):
        repo.save_batch([duplicate])
    db_session.rollback()


def test_same_external_id_different_facility_allowed(db_session) -> None:
    repo = PostgresAssetRepository(db_session)
    r1 = _make_record("facility-a", "EXT-SHARED")
    r2 = _make_record("facility-b", "EXT-SHARED")
    repo.save_batch([r1, r2])

    a_ids = repo.find_existing_external_ids("facility-a", ["EXT-SHARED"])
    b_ids = repo.find_existing_external_ids("facility-b", ["EXT-SHARED"])
    assert a_ids == {"EXT-SHARED"}
    assert b_ids == {"EXT-SHARED"}
