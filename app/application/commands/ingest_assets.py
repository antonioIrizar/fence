from typing import Any

from pydantic import BaseModel


class IngestAssetsCommand(BaseModel):
    facility_id: str
    assets: list[dict[str, Any]]
