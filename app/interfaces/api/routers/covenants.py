from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from app.application.commands.create_facility_report import CreateFacilityReportCommand
from app.application.commands.ingest_assets import IngestAssetsCommand
from app.application.queries.get_facility_state import GetFacilityStateQuery
from app.application.queries.get_report import GetCovenantReportQuery
from app.application.use_cases.create_facility_report import CreateFacilityReportUseCase
from app.application.use_cases.get_covenant_report import (
    GetCovenantReportUseCase,
    ListCovenantReportsUseCase,
)
from app.application.use_cases.get_facility_state import GetFacilityStateUseCase
from app.application.use_cases.ingest_assets import IngestAssetsUseCase
from app.application.use_cases.verify_report import VerifyReportUseCase
from app.domain.covenant.entities import CovenantReport
from app.domain.errors import CovenantCalculationError
from app.interfaces.api.dependencies import (
    get_create_report_use_case,
    get_facility_state_use_case,
    get_ingest_use_case,
    get_list_use_case,
    get_report_use_case,
    get_verify_report_use_case,
)
from app.interfaces.api.schemas.asset import (
    CovenantStateResponse,
    ExcludedAssetResponse,
    FacilityStateResponse,
    FacilityStateSummary,
    IngestAssetsRequest,
    IngestAssetsResponse,
)
from app.interfaces.api.schemas.response import (
    CovenantReportResponse,
    ReportSummary,
    VerifyReportResponse,
)

router = APIRouter(prefix="/api/v1/covenants", tags=["covenants"])


def _to_response(report: CovenantReport) -> CovenantReportResponse:
    return CovenantReportResponse(
        report_id=report.report_id,
        facility_id=report.facility_id,
        effective_rate=str(report.effective_rate),
        threshold=str(report.threshold),
        status=report.status.value,
        summary=ReportSummary(
            total=report.total_assets,
            included=len(report.included_assets),
            excluded=len(report.excluded_assets),
        ),
        included_assets=report.included_assets,
        excluded_assets=[
            ExcludedAssetResponse(
                external_id=e.external_id,
                reasons=e.reasons,
            )
            for e in report.excluded_assets
        ],
        computed_at=report.computed_at,
        audit_hash=report.audit_hash,
    )


@router.post("/{facility_id}/assets", response_model=IngestAssetsResponse)
def ingest_assets(
    facility_id: str,
    body: IngestAssetsRequest,
    use_case: IngestAssetsUseCase = Depends(get_ingest_use_case),
) -> IngestAssetsResponse:
    command = IngestAssetsCommand(facility_id=facility_id, assets=body.assets)
    result = use_case.execute(command)
    return IngestAssetsResponse(
        saved=result.saved,
        duplicates=result.duplicates,
        saved_count=result.saved_count,
        duplicate_count=result.duplicate_count,
        covenant_state=CovenantStateResponse.from_domain(result.covenant_state),
    )


@router.get("/{facility_id}/state", response_model=FacilityStateResponse)
def get_facility_state(
    facility_id: str,
    use_case: GetFacilityStateUseCase = Depends(get_facility_state_use_case),
) -> FacilityStateResponse:
    result = use_case.execute(GetFacilityStateQuery(facility_id=facility_id))
    return FacilityStateResponse(
        covenant_state=CovenantStateResponse.from_domain(result.covenant_state),
        summary=FacilityStateSummary(
            total=result.total_assets,
            included=len(result.included_assets),
            excluded=len(result.excluded_assets),
        ),
        included_assets=result.included_assets,
        excluded_assets=[
            ExcludedAssetResponse(
                external_id=e.external_id,
                reasons=e.reasons,
            )
            for e in result.excluded_assets
        ],
    )


@router.post("/{facility_id}/reports", response_model=CovenantReportResponse)
def create_facility_report(
    facility_id: str,
    x_correlation_id: Optional[str] = Header(default=None),
    force: bool = Query(
        default=False, description="Force a new report even if data is unchanged"
    ),
    use_case: CreateFacilityReportUseCase = Depends(get_create_report_use_case),
) -> CovenantReportResponse:
    """
    Seal the current covenant state as an immutable, auditable report.

    Idempotent by default: if asset data has not changed since the last report,
    the existing report is returned (same audit_hash). Pass ?force=true to seal
    a new record regardless (e.g. after a compliance review event).

    The audit_hash in the response can be independently verified at any time
    by a Capital Provider or Asset Originator via the /verify endpoint.
    """
    correlation_id = x_correlation_id or str(uuid4())
    command = CreateFacilityReportCommand(
        facility_id=facility_id,
        correlation_id=correlation_id,
        force_new=force,
    )
    try:
        report = use_case.execute(command)
    except CovenantCalculationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _to_response(report)


@router.get(
    "/{facility_id}/reports/{report_id}/verify",
    response_model=VerifyReportResponse,
)
def verify_report(
    facility_id: str,
    report_id: UUID,
    use_case: VerifyReportUseCase = Depends(get_verify_report_use_case),
) -> VerifyReportResponse:
    """
    Verify the audit_hash of a sealed report against live PostgreSQL data.

    Returns is_valid=true when the data is intact, false when a discrepancy
    is detected (potential tampering). Callable by Capital Providers and
    Asset Originators at any time without side effects.
    """
    try:
        result = use_case.execute(facility_id=facility_id, report_id=report_id)
    except CovenantCalculationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return VerifyReportResponse(
        report_id=result.report_id,
        facility_id=result.facility_id,
        is_valid=result.is_valid,
        stored_hash=result.stored_hash,
        computed_hash=result.computed_hash,
    )


@router.get("/{facility_id}/reports/{report_id}", response_model=CovenantReportResponse)
def get_covenant_report(
    facility_id: str,
    report_id: UUID,
    use_case: GetCovenantReportUseCase = Depends(get_report_use_case),
) -> CovenantReportResponse:
    query = GetCovenantReportQuery(facility_id=facility_id, report_id=report_id)
    try:
        report = use_case.execute(query)
    except CovenantCalculationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _to_response(report)


@router.get("/{facility_id}/reports", response_model=list[CovenantReportResponse])
def list_covenant_reports(
    facility_id: str,
    use_case: ListCovenantReportsUseCase = Depends(get_list_use_case),
) -> list[CovenantReportResponse]:
    reports = use_case.execute(facility_id)
    return [_to_response(r) for r in reports]
