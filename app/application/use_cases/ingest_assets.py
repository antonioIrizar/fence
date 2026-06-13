from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

from pydantic import BaseModel

from app.application.commands.ingest_assets import IngestAssetsCommand
from app.domain.asset.record import AssetRecord
from app.domain.asset.repository import AssetRepository
from app.domain.errors import InvalidPortfolioData


class IngestAssetsResult(BaseModel):
    """
    Result of an asset ingestion operation.

    - saved: external_ids of newly persisted assets
    - duplicates: external_ids that already existed for this facility
    """

    saved: list[str]
    duplicates: list[str]
    saved_count: int
    duplicate_count: int


def _extract_record(facility_id: str, raw: dict[str, Any]) -> AssetRecord:
    try:
        external_id = str(raw["external_id"])
        status = str(raw.get("status", ""))
        amount = Decimal(str(raw.get("amount", "0")))
        is_eligible = bool(raw.get("is_eligible", False))
    except KeyError as exc:
        raise InvalidPortfolioData(f"Missing required field: {exc}") from exc
    except Exception as exc:
        raise InvalidPortfolioData(f"Invalid asset data: {exc}") from exc

    return AssetRecord(
        id=uuid4(),
        facility_id=facility_id,
        external_id=external_id,
        status=status,
        amount=amount,
        is_eligible=is_eligible,
        raw=raw,
        ingested_at=datetime.now(timezone.utc),
    )


class IngestAssetsUseCase:
    """
    Business context: Accepts a batch of raw asset dicts for a facility,
    deduplicates against already-stored records (by facility_id + external_id),
    persists new assets, and reports which were saved vs skipped.

    Assumptions:
    - Each raw asset must contain an `external_id` field.
    - Duplicates are silently discarded; callers are notified via the result.
    """

    def __init__(self, repository: AssetRepository) -> None:
        self._repository = repository

    def execute(self, command: IngestAssetsCommand) -> IngestAssetsResult:
        records = [_extract_record(command.facility_id, raw) for raw in command.assets]

        if not records:
            return IngestAssetsResult(
                saved=[], duplicates=[], saved_count=0, duplicate_count=0
            )

        all_ids = [r.external_id for r in records]
        existing = self._repository.find_existing_external_ids(
            command.facility_id, all_ids
        )

        new_records = [r for r in records if r.external_id not in existing]
        duplicate_ids = [r.external_id for r in records if r.external_id in existing]

        if new_records:
            self._repository.save_batch(new_records)

        return IngestAssetsResult(
            saved=[r.external_id for r in new_records],
            duplicates=duplicate_ids,
            saved_count=len(new_records),
            duplicate_count=len(duplicate_ids),
        )
