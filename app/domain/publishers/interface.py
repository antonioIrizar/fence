from abc import ABC, abstractmethod

from app.domain.covenant.entities import CovenantReport


class Publisher(ABC):
    """
    Publishes a finalized covenant report to an immutable store.
    Concrete implementations: DatabasePublisher, SmartContractPublisher.
    """

    @abstractmethod
    def publish(self, report: CovenantReport) -> None: ...
