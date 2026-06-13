import logging

from app.domain.covenant.entities import CovenantReport
from app.domain.publishers.interface import Publisher

logger = logging.getLogger(__name__)


class SmartContractPublisher(Publisher):
    """
    Extension point for publishing covenant reports to an on-chain smart contract.

    Production implementation would:
      1. Encode report fields (facility_id, effective_rate, status, timestamp)
         as ABI-typed calldata.
      2. Submit a signed transaction to the CovenantRegistry contract.
      3. Wait for confirmation and store the tx_hash for auditability.

    Currently delegates to logging only — swap in web3.py + contract ABI when ready.
    """

    def publish(self, report: CovenantReport) -> None:
        logger.info(
            "SmartContractPublisher: would publish to chain (stub)",
            extra={
                "facility_id": report.facility_id,
                "covenant_id": str(report.report_id),
                "report_id": str(report.report_id),
                "correlation_id": report.correlation_id,
                "status": report.status.value,
                "effective_rate": str(report.effective_rate),
            },
        )
