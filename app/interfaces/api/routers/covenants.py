from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException
from typing import Optional

from app.application.commands.calculate_covenant import CalculateCovenantCommand
from app.application.commands.ingest_assets import IngestAssetsCommand
from app.application.queries.get_report import GetCovenantReportQuery
from app.application.use_cases.calculate_covenant import CalculateCovenantUseCase
from app.application.use_cases.get_covenant_report import (
    GetCovenantReportUseCase,
    ListCovenantReportsUseCase,
)
from app.application.use_cases.ingest_assets import IngestAssetsUseCase
from app.domain.covenant.entities import CovenantReport
from app.interfaces.api.dependencies import (
    get_calculate_use_case,
    get_ingest_use_case,
    get_list_use_case,
    get_report_use_case,
)
from app.interfaces.api.schemas.asset import IngestAssetsRequest, IngestAssetsResponse
from app.interfaces.api.schemas.request import CalculateCovenantRequest
from app.interfaces.api.schemas.response import (
    CovenantReportResponse,
    ExcludedAssetResponse,
    ReportSummary,
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
    )


@router.post("/{facility_id}/calculate", response_model=CovenantReportResponse)
def calculate_covenant(
    facility_id: str,
    body: CalculateCovenantRequest,
    x_correlation_id: Optional[str] = Header(default=None),
    use_case: CalculateCovenantUseCase = Depends(get_calculate_use_case),
) -> CovenantReportResponse:
    correlation_id = x_correlation_id or str(uuid4())
    command = CalculateCovenantCommand(
        facility_id=facility_id,
        assets=body.assets,
        correlation_id=correlation_id,
    )
    report = use_case.execute(command)
    return _to_response(report)


@router.get("/{facility_id}/reports/{report_id}", response_model=CovenantReportResponse)
def get_covenant_report(
    facility_id: str,
    report_id: UUID,
    use_case: GetCovenantReportUseCase = Depends(get_report_use_case),
) -> CovenantReportResponse:
    query = GetCovenantReportQuery(facility_id=facility_id, report_id=report_id)
    report = use_case.execute(query)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return _to_response(report)


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
    )


@router.get("/{facility_id}/reports", response_model=list[CovenantReportResponse])
def list_covenant_reports(
    facility_id: str,
    use_case: ListCovenantReportsUseCase = Depends(get_list_use_case),
) -> list[CovenantReportResponse]:
    reports = use_case.execute(facility_id)
    return [_to_response(r) for r in reports]
