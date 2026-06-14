from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any

from app.domain.asset.base import BaseAsset
from app.domain.covenant.entities import CovenantReport
from app.domain.facility.processing import AssetProcessingResult


class EligibilityPolicy(ABC):
    """
    Determines whether an asset qualifies for inclusion in the covenant calculation.

    Inputs: a domain asset.
    Outputs: (is_eligible, reasons) — reasons is non-empty only when ineligible.
    """

    @abstractmethod
    def check(self, asset: BaseAsset) -> tuple[bool, list[str]]: ...


class FacilityMapper(ABC):
    """
    Translates raw originator JSON (dict) into a typed domain asset.

    Inputs: raw dict from the originator's portfolio export.
    Outputs: a typed BaseAsset subclass.
    Raises: InvalidPortfolioData on missing or malformed fields.
    """

    @abstractmethod
    def map(self, raw: dict[str, Any]) -> BaseAsset: ...


class FacilityCalculator(ABC):
    """
    Orchestrates eligibility filtering and rate calculation for one facility.

    Inputs: raw asset dicts, facility_id, correlation_id.
    Outputs: CovenantReport (batch) or AssetProcessingResult (per-asset).
    """

    @property
    @abstractmethod
    def threshold(self) -> Decimal:
        """Compliance threshold for this facility's effective rate (as a percentage)."""

    @abstractmethod
    def process_asset(self, raw: dict[str, Any]) -> AssetProcessingResult:
        """
        Map a single raw asset, evaluate eligibility, and compute its
        weighted-average contribution (numerator, denominator) when eligible.

        This is the building block for incremental covenant state updates:
          - Insert: accumulate contribution into the running totals.
          - Future Update: compute delta from stored contribution.

        Raises: InvalidPortfolioData if the raw dict is malformed.
        """

    @abstractmethod
    def calculate(
        self,
        raw_assets: list[dict[str, Any]],
        facility_id: str,
        correlation_id: str,
    ) -> CovenantReport: ...
