from pydantic import BaseModel


class CreateFacilityReportCommand(BaseModel):
    facility_id: str
    correlation_id: str
    force_new: bool = False
