from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.application.services.asset_ingestion_service import AssetIngestionService
from app.domain.asset.base import BaseAsset
from app.domain.errors import InvalidPortfolioData, FacilityNotSupported
from app.domain.facility.processing import AssetProcessingResult


def _raw(external_id: str) -> dict[str, Any]:
    return {"external_id": external_id, "status": "open", "amount": "1000"}


def _asset(external_id: str) -> BaseAsset:
    return BaseAsset(external_id=external_id, amount=Decimal("1000"), is_eligible=True)


def _eligible(external_id: str) -> AssetProcessingResult:
    return AssetProcessingResult(
        asset=_asset(external_id),
        is_eligible=True,
        exclusion_reasons=[],
        numerator=Decimal("20000"),
        denominator=Decimal("1000"),
    )


def _ineligible(external_id: str) -> AssetProcessingResult:
    return AssetProcessingResult(
        asset=_asset(external_id),
        is_eligible=False,
        exclusion_reasons=["status wrong"],
        numerator=None,
        denominator=None,
    )


def _make_service(
    existing_ids: set[str] | None = None,
    process_side_effects: list[AssetProcessingResult] | None = None,
    threshold: Decimal = Decimal("22.00"),
) -> tuple[AssetIngestionService, MagicMock, MagicMock]:
    asset_repo = MagicMock()
    asset_repo.find_existing_external_ids.return_value = existing_ids or set()

    calculator = MagicMock()
    calculator.threshold = threshold
    if process_side_effects:
        calculator.process_asset.side_effect = process_side_effects

    registry = MagicMock()
    registry.get.return_value = calculator

    service = AssetIngestionService(asset_repository=asset_repo, registry=registry)
    return service, asset_repo, calculator


def test_all_new_assets_are_saved() -> None:
    service, repo, calc = _make_service(
        process_side_effects=[_eligible("A1"), _eligible("A2")]
    )
    batch = service.ingest("facility-a", [_raw("A1"), _raw("A2")])

    assert batch.saved_ids == ["A1", "A2"]
    assert batch.duplicate_ids == []
    repo.save_batch.assert_called_once()


def test_duplicates_are_skipped() -> None:
    service, repo, calc = _make_service(
        existing_ids={"A1"},
        process_side_effects=[_eligible("A1"), _eligible("A2")],
    )
    batch = service.ingest("facility-a", [_raw("A1"), _raw("A2")])

    assert batch.saved_ids == ["A2"]
    assert batch.duplicate_ids == ["A1"]
    saved = repo.save_batch.call_args[0][0]
    assert len(saved) == 1 and saved[0].external_id == "A2"


def test_all_duplicates_nothing_saved() -> None:
    service, repo, calc = _make_service(
        existing_ids={"A1", "A2"},
        process_side_effects=[_eligible("A1"), _eligible("A2")],
    )
    batch = service.ingest("facility-a", [_raw("A1"), _raw("A2")])

    assert batch.saved_ids == []
    assert batch.duplicate_ids == ["A1", "A2"]
    repo.save_batch.assert_not_called()


def test_eligible_contributions_collected() -> None:
    service, repo, calc = _make_service(
        process_side_effects=[_eligible("A1"), _eligible("A2")]
    )
    batch = service.ingest("facility-a", [_raw("A1"), _raw("A2")])

    assert len(batch.eligible_contributions) == 2
    assert all(num == Decimal("20000") for num, _ in batch.eligible_contributions)
    assert all(den == Decimal("1000") for _, den in batch.eligible_contributions)


def test_ineligible_assets_have_no_contributions() -> None:
    service, repo, _ = _make_service(process_side_effects=[_ineligible("A1")])
    batch = service.ingest("facility-a", [_raw("A1")])

    # Asset is still saved (persisted for audit), but no contribution
    assert batch.saved_ids == ["A1"]
    assert batch.eligible_contributions == []
    record = repo.save_batch.call_args[0][0][0]
    assert record.is_eligible_asset is False
    assert record.exclusion_reasons == ["status wrong"]


def test_facility_threshold_forwarded() -> None:
    service, _, _ = _make_service(
        process_side_effects=[_eligible("A1")],
        threshold=Decimal("5.00"),
    )
    batch = service.ingest("facility-c", [_raw("A1")])

    assert batch.facility_threshold == Decimal("5.00")


def test_unknown_facility_raises() -> None:
    repo = MagicMock()
    registry = MagicMock()
    registry.get.side_effect = FacilityNotSupported("no calc")
    service = AssetIngestionService(asset_repository=repo, registry=registry)

    with pytest.raises(FacilityNotSupported):
        service.ingest("unknown", [_raw("A1")])


def test_all_records_in_batch_share_same_ingested_at() -> None:
    """Every record produced from one ingest() call must carry the same
    ingested_at timestamp so that the audit hash is deterministic regardless
    of how long the per-asset processing loop takes."""
    service, repo, _ = _make_service(
        process_side_effects=[_eligible("A1"), _eligible("A2")]
    )
    service.ingest("facility-a", [_raw("A1"), _raw("A2")])

    saved = repo.save_batch.call_args[0][0]
    assert len(saved) == 2
    assert saved[0].ingested_at == saved[1].ingested_at


def test_malformed_asset_propagates_error() -> None:
    repo = MagicMock()
    calculator = MagicMock()
    calculator.process_asset.side_effect = InvalidPortfolioData("missing field")
    registry = MagicMock()
    registry.get.return_value = calculator
    service = AssetIngestionService(asset_repository=repo, registry=registry)

    with pytest.raises(InvalidPortfolioData):
        service.ingest("facility-a", [{"no_id": True}])
