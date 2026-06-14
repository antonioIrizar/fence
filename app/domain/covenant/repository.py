from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID


from app.domain.covenant.entities import CovenantReport


class CovenantReportRepository(ABC):
    """
    Domain interface for persisting and retrieving covenant reports.
    Infrastructure provides the concrete implementation.
    """

    @abstractmethod
    def save(self, report: CovenantReport) -> None: ...

    @abstractmethod
    def find_by_id(self, report_id: UUID) -> Optional[CovenantReport]: ...

    @abstractmethod
    def find_by_facility(self, facility_id: str) -> list[CovenantReport]: ...

    @abstractmethod
    def find_latest_by_facility(self, facility_id: str) -> Optional[CovenantReport]: ...
