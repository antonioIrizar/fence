from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ExcludedAssetResponse(BaseModel):
    external_id: str
    reasons: list[str]


class ReportSummary(BaseModel):
    total: int
    included: int
    excluded: int


class CovenantReportResponse(BaseModel):
    report_id: UUID
    facility_id: str
    effective_rate: str
    threshold: str
    status: str
    summary: ReportSummary
    included_assets: list[str]
    excluded_assets: list[ExcludedAssetResponse]
    computed_at: datetime
