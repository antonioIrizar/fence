from fastapi import Request
from fastapi.responses import JSONResponse

from app.domain.errors import (
    CovenantCalculationError,
    CovenantPublicationError,
    FacilityNotSupported,
    InvalidPortfolioData,
)


async def facility_not_supported_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


async def invalid_portfolio_data_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc)})


async def covenant_calculation_error_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": str(exc)})


async def covenant_publication_error_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": str(exc)})


__all__ = [
    "FacilityNotSupported",
    "InvalidPortfolioData",
    "CovenantCalculationError",
    "CovenantPublicationError",
    "facility_not_supported_handler",
    "invalid_portfolio_data_handler",
    "covenant_calculation_error_handler",
    "covenant_publication_error_handler",
]
