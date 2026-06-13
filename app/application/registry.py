from app.domain.errors import FacilityNotSupported
from app.domain.facility.interfaces import FacilityCalculator


class FacilityRegistry:
    """Maps facility IDs to their FacilityCalculator implementations."""

    def __init__(self) -> None:
        self._calculators: dict[str, FacilityCalculator] = {}

    def register(self, facility_id: str, calculator: FacilityCalculator) -> None:
        self._calculators[facility_id] = calculator

    def get(self, facility_id: str) -> FacilityCalculator:
        try:
            return self._calculators[facility_id]
        except KeyError:
            raise FacilityNotSupported(
                f"No calculator registered for facility '{facility_id}'"
            )
