from abc import ABC, abstractmethod

from app.domain.asset.record import AssetRecord


class AssetRepository(ABC):
    """
    Domain interface for persisting and querying raw asset records.

    Implementations must enforce the (facility_id, external_id) uniqueness constraint.
    """

    @abstractmethod
    def save_batch(self, records: list[AssetRecord]) -> None:
        """Persist a batch of new asset records."""

    @abstractmethod
    def find_existing_external_ids(
        self, facility_id: str, external_ids: list[str]
    ) -> set[str]:
        """Return the subset of external_ids already stored for this facility."""

    @abstractmethod
    def find_by_facility(self, facility_id: str) -> list[AssetRecord]:
        """Return all asset records for a facility."""
