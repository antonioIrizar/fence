from pydantic import BaseModel


class GetFacilityStateQuery(BaseModel):
    facility_id: str
