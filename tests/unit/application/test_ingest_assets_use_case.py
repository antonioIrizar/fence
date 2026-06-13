from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.application.commands.ingest_assets import IngestAssetsCommand
from app.application.use_cases.ingest_assets import IngestAssetsUseCase
from app.domain.asset.record import AssetRecord


def _make_raw(external_id: str, status: str = "open") -> dict[str, Any]:
    return {
        "external_id": external_id,
        "status": status,
        "amount": "1000.00",
        "is_eligible": True,
    }


def _make_record(external_id: str) -> AssetRecord:
    return AssetRecord(
        id=uuid4(),
        facility_id="facility-a",
        external_id=external_id,
        status="open",
        amount=Decimal("1000.00"),
        is_eligible=True,
        raw=_make_raw(external_id),
        ingested_at=datetime.now(timezone.utc),
    )


def test_ingest_new_assets_saves_all() -> None:
    repo = MagicMock()
    repo.find_existing_external_ids.return_value = set()

    use_case = IngestAssetsUseCase(repository=repo)
    command = IngestAssetsCommand(
        facility_id="facility-a",
        assets=[_make_raw("A1"), _make_raw("A2")],
    )
    result = use_case.execute(command)

    assert result.saved == ["A1", "A2"]
    assert result.duplicates == []
    assert result.saved_count == 2
    assert result.duplicate_count == 0
    repo.save_batch.assert_called_once()


def test_ingest_skips_duplicates() -> None:
    repo = MagicMock()
    repo.find_existing_external_ids.return_value = {"A1"}

    use_case = IngestAssetsUseCase(repository=repo)
    command = IngestAssetsCommand(
        facility_id="facility-a",
        assets=[_make_raw("A1"), _make_raw("A2")],
    )
    result = use_case.execute(command)

    assert result.saved == ["A2"]
    assert result.duplicates == ["A1"]
    assert result.saved_count == 1
    assert result.duplicate_count == 1
    repo.save_batch.assert_called_once()
    saved_records = repo.save_batch.call_args[0][0]
    assert len(saved_records) == 1
    assert saved_records[0].external_id == "A2"


def test_ingest_all_duplicates_saves_nothing() -> None:
    repo = MagicMock()
    repo.find_existing_external_ids.return_value = {"A1", "A2"}

    use_case = IngestAssetsUseCase(repository=repo)
    command = IngestAssetsCommand(
        facility_id="facility-a",
        assets=[_make_raw("A1"), _make_raw("A2")],
    )
    result = use_case.execute(command)

    assert result.saved == []
    assert result.duplicates == ["A1", "A2"]
    repo.save_batch.assert_not_called()


def test_ingest_missing_external_id_raises() -> None:
    repo = MagicMock()
    repo.find_existing_external_ids.return_value = set()

    use_case = IngestAssetsUseCase(repository=repo)
    command = IngestAssetsCommand(
        facility_id="facility-a",
        assets=[{"status": "open", "amount": "100"}],  # no external_id
    )
    from app.domain.errors import InvalidPortfolioData

    with pytest.raises(InvalidPortfolioData):
        use_case.execute(command)
