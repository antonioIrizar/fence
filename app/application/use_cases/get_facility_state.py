from pydantic import BaseModel

from app.application.queries.get_facility_state import GetFacilityStateQuery
from app.application.services.covenant_state_service import initial_state
from app.domain.asset.repository import AssetRepository
from app.domain.covenant.state import FacilityCovenantState
from app.domain.covenant.state_repository import FacilityCovenantStateRepository


class ExcludedAssetInfo(BaseModel):
    external_id: str
    reasons: list[str]


class FacilityStateResult(BaseModel):
    covenant_state: FacilityCovenantState
    included_assets: list[str]
    excluded_assets: list[ExcludedAssetInfo]

    @property
    def total_assets(self) -> int:
        return len(self.included_assets) + len(self.excluded_assets)


class GetFacilityStateUseCase:
    """
    Business context: Returns a facility's current pre-computed covenant state
    and a breakdown of its ingested assets by eligibility, without triggering
    any recalculation or locking.

    Assumptions:
    - If no covenant state has been persisted yet, a synthetic NO_DATA state is
      returned so callers always receive a well-formed response.
    - Asset eligibility is pre-computed at ingestion time (is_eligible_asset flag);
      this use case only reads and projects that stored result.
    - This operation is fully read-only — no writes, no row locks.
    """

    def __init__(
        self,
        state_repository: FacilityCovenantStateRepository,
        asset_repository: AssetRepository,
    ) -> None:
        self._state_repository = state_repository
        self._asset_repository = asset_repository

    def execute(self, query: GetFacilityStateQuery) -> FacilityStateResult:
        state = self._state_repository.get(query.facility_id) or initial_state(
            query.facility_id
        )
        assets = self._asset_repository.find_by_facility(query.facility_id)

        included = [a.external_id for a in assets if a.is_eligible_asset]
        excluded = [
            ExcludedAssetInfo(
                external_id=a.external_id,
                reasons=a.exclusion_reasons,
            )
            for a in assets
            if not a.is_eligible_asset
        ]

        return FacilityStateResult(
            covenant_state=state,
            included_assets=included,
            excluded_assets=excluded,
        )
