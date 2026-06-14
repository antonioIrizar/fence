from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import uuid4

from app.domain.asset.base import BaseAsset
from app.domain.asset.nomina import NominaAsset
from app.domain.covenant.entities import CovenantReport, CovenantStatus, ExcludedAsset
from app.domain.errors import CovenantCalculationError, InvalidPortfolioData
from app.domain.facility.interfaces import (
    EligibilityPolicy,
    FacilityCalculator,
    FacilityMapper,
)
from app.domain.facility.processing import AssetProcessingResult

_THRESHOLD = Decimal("5.00")
_TWO_PLACES = Decimal("0.01")
_12 = Decimal("12")


def _parse_dd_mm_yyyy(date_str: str) -> date:
    """Parse DD/MM/YYYY date format used by Nomina Express."""
    day, month, year = date_str.split("/")
    return date(int(year), int(month), int(day))


def _repayment_months(origination_date: date, maturity_str: str) -> Decimal:
    """
    Calculate the number of whole calendar months between origination and maturity.
    Uses ceiling to handle partial months (at least 1 month is assumed).
    """
    maturity = _parse_dd_mm_yyyy(maturity_str)
    months = (maturity.year - origination_date.year) * 12 + (
        maturity.month - origination_date.month
    )
    if months < 1:
        months = 1
    return Decimal(str(months))


def _annualized_fee(asset: NominaAsset) -> Decimal:
    months = _repayment_months(asset.origination_date, asset.maturity_date)
    return asset.fee_percentage * (_12 / months)


class NominaEligibilityPolicy(EligibilityPolicy):
    """
    Eligibility rules for Facility C — Nomina Express I (Salary Advance).

    An asset is eligible when ALL hold:
      - status is "active" (case-insensitive)
      - is_eligible is True
      - outstanding_amount > 0
    """

    def check(self, asset: BaseAsset) -> tuple[bool, list[str]]:
        nom = asset if isinstance(asset, NominaAsset) else None
        if nom is None:
            return False, ["asset is not a NominaAsset"]

        reasons: list[str] = []
        if nom.status.lower() != "active":
            reasons.append(f"status must be 'active', got '{nom.status}'")
        if not nom.is_eligible:
            reasons.append("is_eligible is False")
        if nom.outstanding_amount <= Decimal("0"):
            reasons.append(
                f"outstanding_amount must be > 0, got {nom.outstanding_amount}"
            )
        return len(reasons) == 0, reasons


class NominaMapper(FacilityMapper):
    """Maps raw Nomina portfolio JSON to NominaAsset domain objects."""

    def map(self, raw: dict[str, Any]) -> NominaAsset:
        try:
            return NominaAsset(
                external_id=raw["external_id"],
                amount=Decimal(str(raw["amount"])),
                is_eligible=bool(raw["is_eligible"]),
                status=str(raw["status"]),
                outstanding_amount=Decimal(str(raw["outstanding_amount"])),
                fee_percentage=Decimal(str(raw["fee_percentage"])),
                fee_amount=Decimal(str(raw["fee_amount"])),
                origination_date=raw["origination_date"],
                maturity_date=str(raw["maturity_date"]),
                net_monthly_salary=Decimal(str(raw["net_monthly_salary"])),
                advance_amount=Decimal(str(raw["advance_amount"])),
                repaid_amount=Decimal(str(raw["repaid_amount"])),
                days_past_due=int(raw["days_past_due"]),
                employer_name=str(raw["employer_name"]),
                employer_tax_id=str(raw["employer_tax_id"]),
            )
        except KeyError as e:
            raise InvalidPortfolioData(f"Missing required field: {e}") from e
        except Exception as e:
            raise InvalidPortfolioData(f"Invalid portfolio data: {e}") from e


class NominaCalculator(FacilityCalculator):
    """
    Calculates the Weighted Average Annualized Advance Fee for Facility C.

    Formula per eligible asset:
      repayment_months_i = calendar months between origination_date and maturity_date
      annualized_fee_i   = fee_percentage_i × (12 / repayment_months_i)

    Portfolio rate:
      Effective Rate = Σ(outstanding_i × annualized_fee_i) / Σ(outstanding_i)

    Threshold: effective rate must be below 5.0%.
    """

    def __init__(self) -> None:
        self._mapper = NominaMapper()
        self._policy = NominaEligibilityPolicy()

    @property
    def threshold(self) -> Decimal:
        return _THRESHOLD

    def process_asset(self, raw: dict[str, Any]) -> AssetProcessingResult:
        asset = self._mapper.map(raw)
        is_eligible, reasons = self._policy.check(asset)
        if is_eligible:
            assert isinstance(asset, NominaAsset)
            ann_fee = _annualized_fee(asset)
            numerator = asset.outstanding_amount * ann_fee
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
