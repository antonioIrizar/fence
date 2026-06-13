from collections.abc import Generator
from functools import lru_cache

from fastapi import Depends
from sqlalchemy.orm import Session

from app.application.registry import FacilityRegistry
from app.application.use_cases.calculate_covenant import CalculateCovenantUseCase
from app.application.use_cases.get_covenant_report import (
    GetCovenantReportUseCase,
    ListCovenantReportsUseCase,
)
from app.application.use_cases.ingest_assets import IngestAssetsUseCase
from app.domain.asset.repository import AssetRepository
from app.domain.covenant.repository import CovenantReportRepository
from app.domain.publishers.interface import Publisher
from app.infrastructure.database.session import get_session
from app.infrastructure.publishers.database_publisher import DatabasePublisher
from app.infrastructure.publishers.smart_contract_publisher import (
    SmartContractPublisher,
)
from app.infrastructure.repositories.postgres_asset_repository import (
    PostgresAssetRepository,
)
from app.infrastructure.repositories.postgres_covenant_report_repository import (
    PostgresCovenantReportRepository,
)
from app.settings import settings


@lru_cache
def get_registry() -> FacilityRegistry:
    from app.domain.calculations.educa import EducaCalculator
    from app.domain.calculations.nomina import NominaCalculator
    from app.domain.calculations.payearly import PayEarlyCalculator

    registry = FacilityRegistry()
    registry.register("facility-a", EducaCalculator())
    registry.register("facility-b", PayEarlyCalculator())
    registry.register("facility-c", NominaCalculator())
    return registry


def get_db_session() -> Generator[Session, None, None]:
    yield from get_session()


def get_repository(
    session: Session = Depends(get_db_session),
) -> CovenantReportRepository:
    return PostgresCovenantReportRepository(session)


def get_publisher(
    repository: CovenantReportRepository = Depends(get_repository),
) -> Publisher:
    if settings.publisher_backend == "smart_contract":
        return SmartContractPublisher()
    return DatabasePublisher()


def get_calculate_use_case(
    registry: FacilityRegistry = Depends(get_registry),
    repository: CovenantReportRepository = Depends(get_repository),
    publisher: Publisher = Depends(get_publisher),
) -> CalculateCovenantUseCase:
    return CalculateCovenantUseCase(
        registry=registry, repository=repository, publisher=publisher
    )


def get_report_use_case(
    repository: CovenantReportRepository = Depends(get_repository),
) -> GetCovenantReportUseCase:
    return GetCovenantReportUseCase(repository=repository)


def get_list_use_case(
    repository: CovenantReportRepository = Depends(get_repository),
) -> ListCovenantReportsUseCase:
    return ListCovenantReportsUseCase(repository=repository)


def get_asset_repository(
    session: Session = Depends(get_db_session),
) -> AssetRepository:
    return PostgresAssetRepository(session)


def get_ingest_use_case(
    asset_repository: AssetRepository = Depends(get_asset_repository),
) -> IngestAssetsUseCase:
    return IngestAssetsUseCase(repository=asset_repository)
