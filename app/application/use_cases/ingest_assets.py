from pydantic import BaseModel

from app.application.commands.ingest_assets import IngestAssetsCommand
from app.application.services.asset_ingestion_service import (
    AbstractAssetIngestionService,
)
from app.application.services.covenant_state_service import (
    initial_state,
    update_covenant_state,
)
from app.domain.covenant.state import FacilityCovenantState
from app.domain.covenant.state_repository import FacilityCovenantStateRepository


class IngestAssetsResult(BaseModel):
    """
    Result of an asset ingestion batch.

    - saved: external_ids of newly persisted assets (new entries only)
    - duplicates: external_ids that already existed for this facility (skipped)
    - covenant_state: the facility's updated pre-computed covenant state
    """

    saved: list[str]
    duplicates: list[str]
    saved_count: int
    duplicate_count: int
    covenant_state: FacilityCovenantState


class IngestAssetsUseCase:
    """
    Business context: Orchestrates asset ingestion and incremental covenant
    state update for a facility.

    Delegates:
    - Asset processing, deduplication, and persistence → AssetIngestionService
    - Covenant state locking, accumulation, and persistence → update_covenant_state

    Assumptions:
    - Empty asset lists return the current covenant state without acquiring a lock.
    - Only new AND eligible assets contribute to the covenant state delta.
    """

    def __init__(
        self,
        ingestion_service: AbstractAssetIngestionService,
        state_repository: FacilityCovenantStateRepository,
    ) -> None:
        self._ingestion_service = ingestion_service
        self._state_repository = state_repository

    def execute(self, command: IngestAssetsCommand) -> IngestAssetsResult:
        if not command.assets:
            state = self._state_repository.get(command.facility_id) or initial_state(
                command.facility_id
            )
            return IngestAssetsResult(
                saved=[],
                duplicates=[],
                saved_count=0,
                duplicate_count=0,
                covenant_state=state,
            )

        batch = self._ingestion_service.ingest(command.facility_id, command.assets)

        state = update_covenant_state(
            repository=self._state_repository,
            facility_id=command.facility_id,
            contributions=batch.eligible_contributions,
            threshold=batch.facility_threshold,
        )

        return IngestAssetsResult(
            saved=batch.saved_ids,
            duplicates=batch.duplicate_ids,
            saved_count=len(batch.saved_ids),
            duplicate_count=len(batch.duplicate_ids),
            covenant_state=state,
        )
