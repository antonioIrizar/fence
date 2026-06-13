from typing import Optional

from app.application.queries.get_report import GetCovenantReportQuery
from app.domain.covenant.entities import CovenantReport
from app.domain.covenant.repository import CovenantReportRepository


class GetCovenantReportUseCase:
    """
    Business context: Retrieve a previously published covenant report by ID.

    Assumptions:
      - report_id is a valid UUID that was returned from a previous calculation.
    """

    def __init__(self, repository: CovenantReportRepository) -> None:
        self._repository = repository

    def execute(self, query: GetCovenantReportQuery) -> Optional[CovenantReport]:
        return self._repository.find_by_id(query.report_id)


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
