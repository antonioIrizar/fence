from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4
from datetime import datetime, timezone

import pytest

from app.application.commands.calculate_covenant import CalculateCovenantCommand
from app.application.use_cases.calculate_covenant import CalculateCovenantUseCase
from app.domain.covenant.entities import CovenantReport, CovenantStatus
from app.domain.errors import FacilityNotSupported


def _make_report() -> CovenantReport:
    return CovenantReport(
        report_id=uuid4(),
        facility_id="facility-a",
        effective_rate=Decimal("19.43"),
        threshold=Decimal("22.00"),
        status=CovenantStatus.COMPLIANT,
        total_assets=5,
        included_assets=["A1", "A2"],
        excluded_assets=[],
        computed_at=datetime.now(timezone.utc),
        correlation_id="corr-001",
    )


class TestCalculateCovenantUseCase:
    def setup_method(self) -> None:
        self.registry = MagicMock()
        self.repository = MagicMock()
        self.publisher = MagicMock()
        self.use_case = CalculateCovenantUseCase(
            registry=self.registry,
            repository=self.repository,
            publisher=self.publisher,
        )

    def test_execute_returns_report(self) -> None:
        report = _make_report()
        self.registry.get.return_value.calculate.return_value = report

        command = CalculateCovenantCommand(
            facility_id="facility-a",
            assets=[{"external_id": "A1"}],
            correlation_id="corr-001",
        )
        result = self.use_case.execute(command)

        assert result is report

    def test_execute_saves_report(self) -> None:
        report = _make_report()
        self.registry.get.return_value.calculate.return_value = report

        command = CalculateCovenantCommand(
            facility_id="facility-a",
            assets=[],
            correlation_id="corr-001",
        )
        self.use_case.execute(command)

        self.repository.save.assert_called_once_with(report)

    def test_execute_publishes_report(self) -> None:
        report = _make_report()
        self.registry.get.return_value.calculate.return_value = report

        command = CalculateCovenantCommand(
            facility_id="facility-a",
            assets=[],
            correlation_id="corr-001",
        )
        self.use_case.execute(command)

        self.publisher.publish.assert_called_once_with(report)

    def test_execute_propagates_facility_not_supported(self) -> None:
        self.registry.get.side_effect = FacilityNotSupported("facility-x")

        command = CalculateCovenantCommand(
            facility_id="facility-x",
            assets=[],
            correlation_id="corr-001",
        )
        with pytest.raises(FacilityNotSupported):
            self.use_case.execute(command)

    def test_execute_calls_calculator_with_correct_args(self) -> None:
        report = _make_report()
        calculator = self.registry.get.return_value
        calculator.calculate.return_value = report

        assets = [{"external_id": "A1"}, {"external_id": "A2"}]
        command = CalculateCovenantCommand(
            facility_id="facility-a",
            assets=assets,
            correlation_id="corr-xyz",
        )
        self.use_case.execute(command)

        calculator.calculate.assert_called_once_with(assets, "facility-a", "corr-xyz")
