from datetime import datetime, timezone
from uuid import uuid4

from app.application.commands.create_facility_report import CreateFacilityReportCommand
from app.application.registry import FacilityRegistry
from app.domain.asset.repository import AssetRepository
from app.domain.covenant.audit import compute_asset_hash
from app.domain.covenant.entities import CovenantReport, CovenantStatus, ExcludedAsset
from app.domain.covenant.repository import CovenantReportRepository
from app.domain.covenant.state import CovenantStateStatus
from app.domain.covenant.state_repository import FacilityCovenantStateRepository
from app.domain.errors import CovenantCalculationError
from app.domain.publishers.interface import Publisher

_STATUS_MAP = {
    CovenantStateStatus.COMPLIANT: CovenantStatus.COMPLIANT,
    CovenantStateStatus.BREACH: CovenantStatus.BREACH,
}


class CreateFacilityReportUseCase:
    """
    Business context: Materialises the facility's pre-computed covenant state
    into an immutable, auditable report — the PostgreSQL equivalent of a smart
    contract record. Each report carries an audit_hash that proves the asset
    data has not been altered after the report was sealed.

    Assumptions:
    - Raises CovenantCalculationError when no asset data exists (NO_DATA state).
    - Idempotent by default: if the current asset data hash matches the latest
      report's hash the existing report is returned without creating a new row.
    - Pass force_new=True to seal a new report even when data is unchanged
      (e.g. after a compliance review event).
    - The Publisher abstraction is the swap point for a real Web3 smart contract:
      replace DatabasePublisher with SmartContractPublisher in settings to
      notarise the audit_hash on-chain.
    """

    def __init__(
        self,
        state_repository: FacilityCovenantStateRepository,
        asset_repository: AssetRepository,
        registry: FacilityRegistry,
        report_repository: CovenantReportRepository,
        publisher: Publisher,
    ) -> None:
        self._state_repository = state_repository
        self._asset_repository = asset_repository
        self._registry = registry
        self._report_repository = report_repository
        self._publisher = publisher

    def execute(self, command: CreateFacilityReportCommand) -> CovenantReport:
        state = self._state_repository.get_for_update(command.facility_id)
        if state is None or state.covenant_status == CovenantStateStatus.NO_DATA:
            raise CovenantCalculationError(
                f"No asset data available for facility '{command.facility_id}'. "
                "Ingest assets before generating a report."
            )

        assets = self._asset_repository.find_by_facility(command.facility_id)
        audit_hash = compute_asset_hash(command.facility_id, assets, state)

        if not command.force_new:
            latest = self._report_repository.find_latest_by_facility(
                command.facility_id
            )
            if latest is not None and latest.audit_hash == audit_hash:
                return latest

        threshold = self._registry.get(command.facility_id).threshold
        covenant_status = _STATUS_MAP[state.covenant_status]

        included = [a.external_id for a in assets if a.is_eligible_asset]
        excluded = [
            ExcludedAsset(external_id=a.external_id, reasons=a.exclusion_reasons)
            for a in assets
            if not a.is_eligible_asset
        ]

        report = CovenantReport(
            report_id=uuid4(),
            facility_id=command.facility_id,
            effective_rate=state.effective_rate,
            threshold=threshold,
            status=covenant_status,
            total_assets=len(assets),
            included_assets=included,
            excluded_assets=excluded,
            computed_at=datetime.now(timezone.utc),
            correlation_id=command.correlation_id,
            audit_hash=audit_hash,
            accumulated_numerator=state.accumulated_numerator,
            accumulated_denominator=state.accumulated_denominator,
        )

        self._report_repository.save(report)
        self._publisher.publish(report)

        return report
