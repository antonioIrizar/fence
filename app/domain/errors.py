class FacilityNotSupported(Exception):
    """Raised when no calculator is registered for the given facility_id."""


class InvalidPortfolioData(Exception):
    """Raised when raw asset data fails validation or mapping."""


class CovenantCalculationError(Exception):
    """Raised when calculation cannot be completed (e.g. no eligible assets)."""


class CovenantPublicationError(Exception):
    """Raised when a covenant report cannot be persisted or published."""
