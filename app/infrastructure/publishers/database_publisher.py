import logging

from app.domain.covenant.entities import CovenantReport
from app.domain.publishers.interface import Publisher

logger = logging.getLogger(__name__)


class DatabasePublisher(Publisher):
    """
    Publishes a covenant report by marking it as immutably stored in the database.
    The repository.save() call in the use case already persists the row;
    this publisher logs the publication event for auditability.
    """

    def publish(self, report: CovenantReport) -> None:
        logger.info(
            "Covenant report published",
            extra={
                "facility_id": report.facility_id,
                "covenant_id": str(report.report_id),
                "report_id": str(report.report_id),
                "correlation_id": report.correlation_id,
                "status": report.status.value,
                "effective_rate": str(report.effective_rate),
            },
        )
