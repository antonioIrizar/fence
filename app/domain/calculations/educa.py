from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import uuid4

from app.domain.asset.base import BaseAsset
from app.domain.asset.educa import EducaAsset
from app.domain.covenant.entities import CovenantReport, CovenantStatus, ExcludedAsset
from app.domain.errors import CovenantCalculationError, InvalidPortfolioData
from app.domain.facility.interfaces import (
    EligibilityPolicy,
    FacilityCalculator,
    FacilityMapper,
)
from app.domain.facility.processing import AssetProcessingResult

_THRESHOLD = Decimal("22.00")
_TWO_PLACES = Decimal("0.01")


class EducaEligibilityPolicy(EligibilityPolicy):
    """
    Eligibility rules for Facility A — Educa Capital I.

    An asset is eligible when ALL hold:
      - status is "open" (case-insensitive)
      - is_eligible is True
      - loan_status is "current"
      - interest_rate_percentage is not null
    """

    def check(self, asset: BaseAsset) -> tuple[bool, list[str]]:
        educa = asset if isinstance(asset, EducaAsset) else None
        if educa is None:
            return False, ["asset is not an EducaAsset"]

        reasons: list[str] = []
        if educa.status.lower() != "open":
            reasons.append(f"status must be 'open', got '{educa.status}'")
        if not educa.is_eligible:
            reasons.append("is_eligible is False")
        if educa.loan_status != "current":
            reasons.append(f"loan_status must be 'current', got '{educa.loan_status}'")
        if educa.interest_rate_percentage is None:
            reasons.append("interest_rate_percentage is null")
        return len(reasons) == 0, reasons


class EducaMapper(FacilityMapper):
    """Maps raw Educa portfolio JSON to EducaAsset domain objects."""

    def map(self, raw: dict[str, Any]) -> EducaAsset:
        try:
            return EducaAsset(
                external_id=raw["external_id"],
                amount=Decimal(str(raw["amount"])),
                is_eligible=bool(raw["is_eligible"]),
                status=str(raw["status"]),
                loan_status=str(raw["loan_status"]),
                outstanding_amount=Decimal(str(raw["outstanding_amount"])),
                interest_rate_percentage=(
                    Decimal(str(raw["interest_rate_percentage"]))
                    if raw.get("interest_rate_percentage") is not None
                    else None
                ),
                effective_date=raw["effective_date"],
                reporting_date=raw["reporting_date"],
                student_id=str(raw["student_id"]),
                school_id=str(raw["school_id"]),
                disbursement_amount=Decimal(str(raw["disbursement_amount"])),
                repaid_amount=Decimal(str(raw["repaid_amount"])),
                days_past_due=int(raw["days_past_due"]),
                country=str(raw["country"]),
            )
        except KeyError as e:
            raise InvalidPortfolioData(f"Missing required field: {e}") from e
        except Exception as e:
            raise InvalidPortfolioData(f"Invalid portfolio data: {e}") from e


class EducaCalculator(FacilityCalculator):
    """
    Calculates the Weighted Average Loan IRR for Facility A — Educa Capital I.

    Formula: Σ(outstanding_i × rate_i) / Σ(outstanding_i)
    Threshold: effective rate must be below 22.0%.
    """

    def __init__(self) -> None:
        self._mapper = EducaMapper()
        self._policy = EducaEligibilityPolicy()

    @property
    def threshold(self) -> Decimal:
        return _THRESHOLD

    def process_asset(self, raw: dict[str, Any]) -> AssetProcessingResult:
        asset = self._mapper.map(raw)
        is_eligible, reasons = self._policy.check(asset)
        if is_eligible:
            assert asset.interest_rate_percentage is not None
            numerator = asset.outstanding_amount * asset.interest_rate_percentage
            denominator = asset.outstanding_amount
            return AssetProcessingResult(
                asset=asset,
                is_eligible=True,
                exclusion_reasons=[],
                numerator=numerator,
                denominator=denominator,
            )
        return AssetProcessingResult(
            asset=asset,
            is_eligible=False,
            exclusion_reasons=reasons,
            numerator=None,
            denominator=None,
        )

    def calculate(
        self,
        raw_assets: list[dict[str, Any]],
        facility_id: str,
        correlation_id: str,
    ) -> CovenantReport:
        included: list[str] = []
        excluded: list[ExcludedAsset] = []
        weighted_sum = Decimal("0")
        total_outstanding = Decimal("0")

        for raw in raw_assets:
            result = self.process_asset(raw)
            if result.is_eligible:
                included.append(result.asset.external_id)
                assert result.numerator is not None
                assert result.denominator is not None
                weighted_sum += result.numerator
                total_outstanding += result.denominator
            else:
                excluded.append(
                    ExcludedAsset(
                        external_id=result.asset.external_id,
                        reasons=result.exclusion_reasons,
                    )
                )

        if total_outstanding == Decimal("0"):
            raise CovenantCalculationError(
                f"No eligible assets found for facility '{facility_id}'"
            )

        effective_rate = (weighted_sum / total_outstanding).quantize(
            _TWO_PLACES, rounding=ROUND_HALF_UP
        )
        status = (
            CovenantStatus.COMPLIANT
            if effective_rate < _THRESHOLD
            else CovenantStatus.BREACH
        )

        return CovenantReport(
            report_id=uuid4(),
            facility_id=facility_id,
            effective_rate=effective_rate,
            threshold=_THRESHOLD,
            status=status,
            total_assets=len(raw_assets),
            included_assets=included,
            excluded_assets=excluded,
            computed_at=datetime.now(timezone.utc),
            correlation_id=correlation_id,
        )
