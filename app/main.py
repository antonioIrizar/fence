from fastapi import FastAPI

from app.domain.errors import (
    CovenantCalculationError,
    CovenantPublicationError,
    FacilityNotSupported,
    InvalidPortfolioData,
)
from app.interfaces.api.exception_handlers import (
    covenant_calculation_error_handler,
    covenant_publication_error_handler,
    facility_not_supported_handler,
    invalid_portfolio_data_handler,
)
from app.interfaces.api.routers.covenants import router as covenants_router

app = FastAPI(
    title="Fence Covenant Calculation Platform",
    description="Automates covenant compliance for credit facilities.",
    version="0.1.0",
)

app.add_exception_handler(FacilityNotSupported, facility_not_supported_handler)
app.add_exception_handler(InvalidPortfolioData, invalid_portfolio_data_handler)
app.add_exception_handler(CovenantCalculationError, covenant_calculation_error_handler)
app.add_exception_handler(CovenantPublicationError, covenant_publication_error_handler)

app.include_router(covenants_router)
