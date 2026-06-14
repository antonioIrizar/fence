from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.application.commands.ingest_assets import IngestAssetsCommand
from app.application.services.asset_ingestion_service import AssetIngestionBatch
from app.application.use_cases.ingest_assets import IngestAssetsUseCase
from app.domain.covenant.state import CovenantStateStatus, FacilityCovenantState


def _state(
    facility_id: str = "facility-a",
    status: CovenantStateStatus = CovenantStateStatus.COMPLIANT,
    effective_rate: str = "19.00",
) -> FacilityCovenantState:
    return FacilityCovenantState(
        id=uuid4(),
        facility_id=facility_id,
        accumulated_numerator=Decimal("190000"),
        accumulated_denominator=Decimal("10000"),
        effective_rate=Decimal(effective_rate),
        covenant_status=status,
        last_updated=datetime.now(timezone.utc),
    )


def _batch(
    saved: list[str] | None = None,
    duplicates: list[str] | None = None,
    contributions: list[tuple[Decimal, Decimal]] | None = None,
    threshold: Decimal = Decimal("22.00"),
) -> AssetIngestionBatch:
    return AssetIngestionBatch(
        saved_ids=saved or [],
        duplicate_ids=duplicates or [],
        eligible_contributions=contributions or [],
        facility_threshold=threshold,
    )


def _make_use_case(
    batch: AssetIngestionBatch | None = None,
    updated_state: FacilityCovenantState | None = None,
    current_state: FacilityCovenantState | None = None,
) -> tuple[IngestAssetsUseCase, MagicMock, MagicMock]:
    ingestion_service = MagicMock()
    ingestion_service.ingest.return_value = batch or _batch()

    state_repo = MagicMock()
    state_repo.get.return_value = current_state

    use_case = IngestAssetsUseCase(
        ingestion_service=ingestion_service,
        state_repository=state_repo,
    )
    return use_case, ingestion_service, state_repo


# ── orchestration ─────────────────────────────────────────────────────────────


def test_delegates_to_ingestion_service() -> None:
    use_case, service, _ = _make_use_case(
        batch=_batch(saved=["A1", "A2"]),
    )
    with patch(
        "app.application.use_cases.ingest_assets.update_covenant_state",
        return_value=_state(),
    ):
        result = use_case.execute(
            IngestAssetsCommand(
                facility_id="facility-a",
                assets=[{"external_id": "A1"}, {"external_id": "A2"}],
            )
        )

    service.ingest.assert_called_once_with(
        "facility-a", [{"external_id": "A1"}, {"external_id": "A2"}]
    )
    assert result.saved == ["A1", "A2"]
    assert result.saved_count == 2


def test_calls_update_covenant_state_with_contributions() -> None:
    contributions = [(Decimal("95000"), Decimal("5000"))]
    use_case, _, _ = _make_use_case(
        batch=_batch(
            saved=["A1"], contributions=contributions, threshold=Decimal("22.00")
        )
    )

    with patch(
        "app.application.use_cases.ingest_assets.update_covenant_state",
        return_value=_state(),
    ) as mock_update:
        use_case.execute(
            IngestAssetsCommand(
                facility_id="facility-a", assets=[{"external_id": "A1"}]
            )
        )

    mock_update.assert_called_once()
    _, call_kwargs = mock_update.call_args
    assert call_kwargs["contributions"] == contributions
    assert call_kwargs["threshold"] == Decimal("22.00")


def test_result_contains_covenant_state() -> None:
    expected = _state(status=CovenantStateStatus.BREACH)
    use_case, _, _ = _make_use_case(batch=_batch(saved=["A1"]))

    with patch(
        "app.application.use_cases.ingest_assets.update_covenant_state",
        return_value=expected,
    ):
        result = use_case.execute(
            IngestAssetsCommand(
                facility_id="facility-a", assets=[{"external_id": "A1"}]
            )
        )

    assert result.covenant_state is expected
    assert result.covenant_state.covenant_status == CovenantStateStatus.BREACH


def test_duplicates_forwarded_to_result() -> None:
    use_case, _, _ = _make_use_case(batch=_batch(saved=["A2"], duplicates=["A1"]))

    with patch(
        "app.application.use_cases.ingest_assets.update_covenant_state",
        return_value=_state(),
    ):
        result = use_case.execute(
            IngestAssetsCommand(
                facility_id="facility-a",
                assets=[{"external_id": "A1"}, {"external_id": "A2"}],
            )
        )

    assert result.duplicates == ["A1"]
    assert result.duplicate_count == 1


# ── empty batch ───────────────────────────────────────────────────────────────


def test_empty_assets_skips_ingestion_and_returns_current_state() -> None:
    current = _state(status=CovenantStateStatus.NO_DATA)
    use_case, service, state_repo = _make_use_case(current_state=current)

    result = use_case.execute(IngestAssetsCommand(facility_id="facility-a", assets=[]))

    service.ingest.assert_not_called()
    state_repo.get.assert_called_once_with("facility-a")
    assert result.saved == []
    assert result.covenant_state is current


def test_empty_assets_creates_initial_state_when_none() -> None:
    use_case, _, state_repo = _make_use_case(current_state=None)
    state_repo.get.return_value = None

    result = use_case.execute(IngestAssetsCommand(facility_id="facility-a", assets=[]))

    assert result.covenant_state.facility_id == "facility-a"
    assert result.covenant_state.covenant_status == CovenantStateStatus.NO_DATA
