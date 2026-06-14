from datetime import datetime
from typing import Optional
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
    audit_hash: Optional[str] = None


class VerifyReportResponse(BaseModel):
    report_id: UUID
    facility_id: str
    is_valid: bool
    stored_hash: str
    computed_hash: str
