from typing import Any

from pydantic import BaseModel


class CalculateCovenantRequest(BaseModel):
    assets: list[dict[str, Any]]
