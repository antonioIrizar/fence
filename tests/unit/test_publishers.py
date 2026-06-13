from decimal import Decimal
from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import MagicMock

import pytest

from app.domain.covenant.entities import CovenantReport, CovenantStatus
from app.infrastructure.publishers.database_publisher import DatabasePublisher
from app.infrastructure.publishers.smart_contract_publisher import (
    SmartContractPublisher,
)
from app.domain.errors import CovenantPublicationError
from app.infrastructure.repositories.postgres_covenant_report_repository import (
    PostgresCovenantReportRepository,
)


def _make_report() -> CovenantReport:
    return CovenantReport(
        report_id=uuid4(),
        facility_id="facility-a",
        effective_rate=Decimal("19.43"),
        threshold=Decimal("22.00"),
        status=CovenantStatus.COMPLIANT,
        total_assets=3,
        included_assets=["A1"],
        excluded_assets=[],
        computed_at=datetime.now(timezone.utc),
        correlation_id="corr-001",
    )


class TestDatabasePublisher:
    def test_publish_logs_without_error(self) -> None:
        publisher = DatabasePublisher()
        publisher.publish(_make_report())  # should not raise


class TestSmartContractPublisher:
    def test_publish_logs_stub_without_error(self) -> None:
        publisher = SmartContractPublisher()
        publisher.publish(_make_report())  # should not raise


class TestRepositorySaveError:
    def test_save_wraps_exception_as_publication_error(self) -> None:
        session = MagicMock()
        session.add.side_effect = Exception("DB connection lost")
        repo = PostgresCovenantReportRepository(session)
        with pytest.raises(CovenantPublicationError, match="Failed to save"):
            repo.save(_make_report())
