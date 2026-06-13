from app.application.commands.calculate_covenant import CalculateCovenantCommand
from app.application.registry import FacilityRegistry
from app.domain.covenant.entities import CovenantReport
from app.domain.covenant.repository import CovenantReportRepository
from app.domain.publishers.interface import Publisher


class CalculateCovenantUseCase:
    """
    Business context: Ingest raw portfolio data, compute the facility's effective
    interest rate, produce an auditable CovenantReport, and publish it immutably.

    Assumptions:
      - facility_id is registered in the FacilityRegistry.
      - Raw asset dicts are validated by the facility's FacilityMapper.
      - Each execution creates a new, independent report (append-only).
    """

    def __init__(
        self,
        registry: FacilityRegistry,
        repository: CovenantReportRepository,
        publisher: Publisher,
    ) -> None:
        self._registry = registry
        self._repository = repository
        self._publisher = publisher

    def execute(self, command: CalculateCovenantCommand) -> CovenantReport:
        calculator = self._registry.get(command.facility_id)
        report = calculator.calculate(
            command.assets, command.facility_id, command.correlation_id
        )
        self._repository.save(report)
        self._publisher.publish(report)
        return report
