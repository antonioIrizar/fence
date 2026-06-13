from typing import Any

from pydantic import BaseModel


class CalculateCovenantCommand(BaseModel):
    facility_id: str
    assets: list[dict[str, Any]]
    correlation_id: str
