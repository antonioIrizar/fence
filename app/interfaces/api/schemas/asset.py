from typing import Any

from pydantic import BaseModel


class IngestAssetsRequest(BaseModel):
    assets: list[dict[str, Any]]


class IngestAssetsResponse(BaseModel):
    saved: list[str]
    duplicates: list[str]
    saved_count: int
    duplicate_count: int
