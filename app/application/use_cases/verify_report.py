from dataclasses import dataclass
from uuid import UUID, uuid4

from app.domain.asset.repository import AssetRepository
from app.domain.covenant.audit import compute_asset_hash
from app.domain.covenant.entities import CovenantReport, CovenantStatus
from app.domain.covenant.repository import CovenantReportRepository
from app.domain.covenant.state import CovenantStateStatus, FacilityCovenantState
from app.domain.errors import CovenantCalculationError


@dataclass
class VerifyReportResult:
    """
    Outcome of an audit-hash verification.

    is_valid=True means asset data in PostgreSQL is identical to what was
    present when the report was sealed. is_valid=False means data was altered
    after the report was created — a tamper signal.
    """

    report_id: UUID
    facility_id: str
    is_valid: bool
    stored_hash: str
    computed_hash: str


_STATUS_MAP = {
    CovenantStatus.COMPLIANT: CovenantStateStatus.COMPLIANT,
    CovenantStatus.BREACH: CovenantStateStatus.BREACH,
}


class VerifyReportUseCase:
    """
    Business context: Allows Capital Providers and Asset Originators to verify
    at any time that the asset data in PostgreSQL has not been altered since a
    specific report was sealed.

    Re-computes the audit_hash from the point-in-time asset snapshot
    (assets ingested on or before report.computed_at) and the covenant state
    as it existed at that moment (reconstructed from those same assets).
    Comparing the result with the stored hash proves data integrity without
    requiring an external state query — the report itself is the source of truth.

    Assumptions:
    - Raises CovenantCalculationError if the report does not exist.
    - A mismatch does not raise an error — it returns is_valid=False so the
      caller can decide how to respond.
    - Assets are append-only: existing assets cannot be modified, only new ones
      inserted. This guarantees that the snapshot retrieved via find_by_facility_at
      is identical to what existed when the report was sealed.
    """

    def __init__(
        self,
        report_repository: CovenantReportRepository,
        asset_repository: AssetRepository,
    ) -> None:
        self._report_repository = report_repository
        self._asset_repository = asset_repository

    def execute(self, facility_id: str, report_id: UUID) -> VerifyReportResult:
        report = self._report_repository.find_by_id(report_id)
        if report is None:
            raise CovenantCalculationError(
                f"Report '{report_id}' not found for facility '{facility_id}'."
            )
        if report.facility_id != facility_id:
            raise CovenantCalculationError(
                f"Report '{report_id}' does not belong to facility '{facility_id}'."
            )
        assets = self._asset_repository.find_by_facility_at(
            facility_id, report.computed_at
        )

        state = _reconstruct_state(facility_id, report)
        computed = compute_asset_hash(facility_id, assets, state)

        return VerifyReportResult(
            report_id=report_id,
            facility_id=facility_id,
            is_valid=computed == report.audit_hash,
            stored_hash=report.audit_hash,
            computed_hash=computed,
        )


def _reconstruct_state(
    facility_id: str,
    report: CovenantReport,
) -> FacilityCovenantState:
    """
    Rebuilds the FacilityCovenantState as it existed when the report was sealed.

    Uses the accumulated_numerator and accumulated_denominator stored in the
    report itself — these were copied directly from the live FacilityCovenantState
    at creation time, so they carry exact Decimal precision and are immune to the
    truncation that affects individually-stored asset contribution fields.
    """
    return FacilityCovenantState(
        id=uuid4(),
        facility_id=facility_id,
        accumulated_numerator=report.accumulated_numerator,
        accumulated_denominator=report.accumulated_denominator,
        effective_rate=report.effective_rate,
        covenant_status=_STATUS_MAP[report.status],
        last_updated=report.computed_at,
    )
