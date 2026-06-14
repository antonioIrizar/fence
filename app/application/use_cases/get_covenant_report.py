from app.application.queries.get_report import GetCovenantReportQuery
from app.domain.covenant.entities import CovenantReport
from app.domain.covenant.repository import CovenantReportRepository
from app.domain.errors import CovenantCalculationError


class GetCovenantReportUseCase:
    """
    Business context: Retrieve a previously published covenant report by ID.

    Assumptions:
      - report_id is a valid UUID that was returned from a previous calculation.
      - Raises CovenantCalculationError if the report does not exist or belongs
        to a different facility (IDOR guard).
    """

    def __init__(self, repository: CovenantReportRepository) -> None:
        self._repository = repository

    def execute(self, query: GetCovenantReportQuery) -> CovenantReport:
        report = self._repository.find_by_id(query.report_id)
        if report is None:
            raise CovenantCalculationError(
                f"Report '{query.report_id}' not found "
                f"for facility '{query.facility_id}'."
            )
        if report.facility_id != query.facility_id:
            raise CovenantCalculationError(
                f"Report '{query.report_id}' does not belong "
                f"to facility '{query.facility_id}'."
            )
        return report


class ListCovenantReportsUseCase:
    """
    Business context: List all published covenant reports for a facility.

    Assumptions:
      - facility_id corresponds to a known facility.
    """

    def __init__(self, repository: CovenantReportRepository) -> None:
        self._repository = repository

    def execute(self, facility_id: str) -> list[CovenantReport]:
        return self._repository.find_by_facility(facility_id)
