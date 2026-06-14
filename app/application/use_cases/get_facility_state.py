from dataclasses import dataclass

from app.application.services.covenant_state_service import initial_state
from app.domain.asset.repository import AssetRepository
from app.domain.covenant.state import FacilityCovenantState
from app.domain.covenant.state_repository import FacilityCovenantStateRepository


@dataclass
class ExcludedAssetInfo:
    external_id: str
    reasons: list[str]


@dataclass
class FacilityStateResult:
    covenant_state: FacilityCovenantState
    included_assets: list[str]
    excluded_assets: list[ExcludedAssetInfo]

    @property
    def total_assets(self) -> int:
        return len(self.included_assets) + len(self.excluded_assets)


class GetFacilityStateUseCase:
    """
    Read-only query: returns the pre-computed covenant state for a facility
    together with the list of included and excluded assets derived from the
    ingested asset records. Never writes to the database.
    """

    def __init__(
        self,
        state_repository: FacilityCovenantStateRepository,
        asset_repository: AssetRepository,
    ) -> None:
        self._state_repository = state_repository
        self._asset_repository = asset_repository

    def execute(self, facility_id: str) -> FacilityStateResult:
        state = self._state_repository.get(facility_id) or initial_state(facility_id)
        assets = self._asset_repository.find_by_facility(facility_id)

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
