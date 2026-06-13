from uuid import UUID

from pydantic import BaseModel


class GetCovenantReportQuery(BaseModel):
    facility_id: str
    report_id: UUID
