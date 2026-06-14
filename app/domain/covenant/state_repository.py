from abc import ABC, abstractmethod
from typing import Optional

from app.domain.covenant.state import FacilityCovenantState


class FacilityCovenantStateRepository(ABC):
    """
    Domain interface for reading and updating the per-facility covenant state.

    `get_for_update` acquires a row-level exclusive lock (SELECT FOR UPDATE)
    to prevent concurrent modifications from producing race conditions on the
    accumulated numerator / denominator.
    """

    @abstractmethod
    def get(self, facility_id: str) -> Optional[FacilityCovenantState]:
        """Read-only fetch — no lock acquired."""

    @abstractmethod
    def get_for_update(self, facility_id: str) -> Optional[FacilityCovenantState]:
        """Fetch with an exclusive row-level lock for safe in-place update."""

    @abstractmethod
    def upsert(self, state: FacilityCovenantState) -> None:
        """Create or overwrite the state row for this facility."""
