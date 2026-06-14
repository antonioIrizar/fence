from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

from pydantic import BaseModel

from app.application.registry import FacilityRegistry
from app.domain.asset.record import AssetRecord
from app.domain.asset.repository import AssetRepository
from app.domain.facility.processing import AssetProcessingResult


class AssetIngestionBatch(BaseModel):
    """
    Outcome of processing one raw-asset batch through the facility pipeline.

    - saved_ids: external_ids of newly persisted records
    - duplicate_ids: external_ids that already existed for this facility
    - eligible_contributions: (numerator, denominator) pairs for each new
      eligible asset; used to update the FacilityCovenantState incrementally
    - facility_threshold: the compliance boundary for this facility
    """

    saved_ids: list[str]
    duplicate_ids: list[str]
    eligible_contributions: list[tuple[Decimal, Decimal]]
    facility_threshold: Decimal


def _build_record(
    facility_id: str,
    raw: dict[str, Any],
    result: AssetProcessingResult,
) -> AssetRecord:
    return AssetRecord(
        id=uuid4(),
        facility_id=facility_id,
        external_id=result.asset.external_id,
        amount=result.asset.amount,
        is_eligible=result.asset.is_eligible,
        status=str(raw.get("status", "")),
        raw=raw,
        ingested_at=datetime.now(timezone.utc),
        is_eligible_asset=result.is_eligible,
        exclusion_reasons=result.exclusion_reasons,
        contribution_numerator=result.numerator,
        contribution_denominator=result.denominator,
    )


class AssetIngestionService:
    """
    Application service responsible for processing, deduplicating, and
    persisting a batch of raw assets for a facility.

    Uses the FacilityCalculator (via the registry) to:
      1. Map each raw dict to a typed domain asset.
      2. Evaluate facility-specific eligibility rules.
      3. Compute the asset's weighted-average contribution when eligible.

    Returns an AssetIngestionBatch so the caller can update the
    FacilityCovenantState without re-processing the assets.
    """

    def __init__(
        self,
        asset_repository: AssetRepository,
        registry: FacilityRegistry,
    ) -> None:
        self._asset_repository = asset_repository
        self._registry = registry

    def ingest(
        self, facility_id: str, raw_assets: list[dict[str, Any]]
    ) -> AssetIngestionBatch:
        calculator = self._registry.get(facility_id)

        processed = [(raw, calculator.process_asset(raw)) for raw in raw_assets]

        all_ids = [r.asset.external_id for _, r in processed]
        existing = self._asset_repository.find_existing_external_ids(
            facility_id, all_ids
        )

        new_pairs = [
            (raw, r) for raw, r in processed if r.asset.external_id not in existing
        ]
        duplicate_ids = [
            r.asset.external_id for _, r in processed if r.asset.external_id in existing
        ]

        new_records = [_build_record(facility_id, raw, r) for raw, r in new_pairs]
        if new_records:
            self._asset_repository.save_batch(new_records)

        contributions = [
            (r.numerator, r.denominator)
            for _, r in new_pairs
            if r.is_eligible and r.numerator is not None and r.denominator is not None
        ]

        return AssetIngestionBatch(
            saved_ids=[rec.external_id for rec in new_records],
            duplicate_ids=duplicate_ids,
            eligible_contributions=contributions,
            facility_threshold=calculator.threshold,
        )
