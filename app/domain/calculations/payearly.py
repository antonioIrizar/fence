from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import uuid4

from app.domain.asset.base import BaseAsset
from app.domain.asset.payearly import PayEarlyAsset
from app.domain.covenant.entities import CovenantReport, CovenantStatus, ExcludedAsset
from app.domain.errors import CovenantCalculationError, InvalidPortfolioData
from app.domain.facility.interfaces import (
    EligibilityPolicy,
    FacilityCalculator,
    FacilityMapper,
)
from app.domain.facility.processing import AssetProcessingResult

_THRESHOLD = Decimal("3.00")
_TWO_PLACES = Decimal("0.01")
_365 = Decimal("365")


def _fee_yield_pct(asset: PayEarlyAsset) -> Decimal:
    """
    Annualised fee yield as a percentage.
    fee_yield = (total_fee / total_principal) × (365 / tenor_days) × 100
    """
    tenor_days = Decimal(str((asset.due_date - asset.created_at.date()).days))
    fee_yield = (asset.total_fee_amount / asset.total_principal_amount) * (
        _365 / tenor_days
    )
    return fee_yield * Decimal("100")


class PayEarlyEligibilityPolicy(EligibilityPolicy):
    """
    Eligibility rules for Facility B — PayEarly US (Earned Wage Access).

    An asset is eligible when ALL hold:
      - status is "performing" (case-insensitive)
      - is_eligible is True
      - outstanding_principal_amount > 0
    """

    def check(self, asset: BaseAsset) -> tuple[bool, list[str]]:
        pe = asset if isinstance(asset, PayEarlyAsset) else None
        if pe is None:
            return False, ["asset is not a PayEarlyAsset"]

        reasons: list[str] = []
        if pe.status.lower() != "performing":
            reasons.append(f"status must be 'performing', got '{pe.status}'")
        if not pe.is_eligible:
            reasons.append("is_eligible is False")
        if pe.outstanding_principal_amount <= Decimal("0"):
            reasons.append(
                "outstanding_principal_amount must be > 0, "
                f"got {pe.outstanding_principal_amount}"
            )
        return len(reasons) == 0, reasons


class PayEarlyMapper(FacilityMapper):
    """Maps raw PayEarly portfolio JSON to PayEarlyAsset domain objects."""

    def map(self, raw: dict[str, Any]) -> PayEarlyAsset:
        try:
            return PayEarlyAsset(
                external_id=raw["external_id"],
                amount=Decimal(str(raw["amount"])),
                is_eligible=bool(raw["is_eligible"]),
                status=str(raw["status"]),
                outstanding_principal_amount=Decimal(
                    str(raw["outstanding_principal_amount"])
                ),
                total_principal_amount=Decimal(str(raw["total_principal_amount"])),
                repaid_principal_amount=Decimal(str(raw["repaid_principal_amount"])),
                total_fee_amount=Decimal(str(raw["total_fee_amount"])),
                outstanding_fee_amount=Decimal(str(raw["outstanding_fee_amount"])),
                created_at=raw["created_at"],
                due_date=raw["due_date"],
                days_past_due=int(raw["days_past_due"]),
                receivable_currency=str(raw["receivable_currency"]),
                employer_id=str(raw["employer_id"]),
                employer_name=str(raw["employer_name"]),
                employee_id=str(raw["employee_id"]),
                user_state=str(raw["user_state"]),
            )
        except KeyError as e:
            raise InvalidPortfolioData(f"Missing required field: {e}") from e
        except Exception as e:
            raise InvalidPortfolioData(f"Invalid portfolio data: {e}") from e


class PayEarlyCalculator(FacilityCalculator):
    """
    Calculates the Portfolio Fee Yield for Facility B — PayEarly US.

    EWA products carry 0% interest; the effective rate is derived from the fee
    structure relative to outstanding principal, annualized by loan tenor.

    Formula per eligible asset:
      tenor_days_i = (due_date - created_at.date()).days
      fee_yield_i  = (total_fee_i / total_principal_i) × (365 / tenor_days_i)

    Portfolio rate:
      Effective Rate = Σ(outstanding_i × fee_yield_i) / Σ(outstanding_i)

    Threshold: effective rate must be below 3.0%.
    """

    def __init__(self) -> None:
        self._mapper = PayEarlyMapper()
        self._policy = PayEarlyEligibilityPolicy()

    @property
    def threshold(self) -> Decimal:
        return _THRESHOLD

    def process_asset(self, raw: dict[str, Any]) -> AssetProcessingResult:
        asset = self._mapper.map(raw)
        is_eligible, reasons = self._policy.check(asset)
        if is_eligible:
            assert isinstance(asset, PayEarlyAsset)
            fee_yield_pct = _fee_yield_pct(asset)
            numerator = asset.outstanding_principal_amount * fee_yield_pct
            denominator = asset.outstanding_principal_amount
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
