from collections.abc import Generator
from functools import lru_cache

from fastapi import Depends
from sqlalchemy.orm import Session

from app.application.registry import FacilityRegistry
from app.application.use_cases.get_covenant_report import (
    GetCovenantReportUseCase,
    ListCovenantReportsUseCase,
)
from app.application.services.asset_ingestion_service import AssetIngestionService
from app.application.use_cases.create_facility_report import CreateFacilityReportUseCase
from app.application.use_cases.get_facility_state import GetFacilityStateUseCase
from app.application.use_cases.ingest_assets import IngestAssetsUseCase
from app.application.use_cases.verify_report import VerifyReportUseCase
from app.domain.asset.repository import AssetRepository
from app.domain.covenant.repository import CovenantReportRepository
from app.domain.covenant.state_repository import FacilityCovenantStateRepository
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
from app.infrastructure.repositories.postgres_facility_covenant_state_repository import (  # noqa: E501
    PostgresFacilityCovenantStateRepository,
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


def get_covenant_state_repository(
    session: Session = Depends(get_db_session),
) -> FacilityCovenantStateRepository:
    return PostgresFacilityCovenantStateRepository(session)


def get_asset_ingestion_service(
    asset_repository: AssetRepository = Depends(get_asset_repository),
    registry: FacilityRegistry = Depends(get_registry),
) -> AssetIngestionService:
    return AssetIngestionService(
        asset_repository=asset_repository,
        registry=registry,
    )


def get_create_report_use_case(
    state_repository: FacilityCovenantStateRepository = Depends(
        get_covenant_state_repository
    ),
    asset_repository: AssetRepository = Depends(get_asset_repository),
    registry: FacilityRegistry = Depends(get_registry),
    report_repository: CovenantReportRepository = Depends(get_repository),
    publisher: Publisher = Depends(get_publisher),
) -> CreateFacilityReportUseCase:
    return CreateFacilityReportUseCase(
        state_repository=state_repository,
        asset_repository=asset_repository,
        registry=registry,
        report_repository=report_repository,
        publisher=publisher,
    )


def get_verify_report_use_case(
    report_repository: CovenantReportRepository = Depends(get_repository),
    asset_repository: AssetRepository = Depends(get_asset_repository),
) -> VerifyReportUseCase:
    return VerifyReportUseCase(
        report_repository=report_repository,
        asset_repository=asset_repository,
    )


def get_facility_state_use_case(
    state_repository: FacilityCovenantStateRepository = Depends(
        get_covenant_state_repository
    ),
    asset_repository: AssetRepository = Depends(get_asset_repository),
) -> GetFacilityStateUseCase:
    return GetFacilityStateUseCase(
        state_repository=state_repository,
        asset_repository=asset_repository,
    )


def get_ingest_use_case(
    ingestion_service: AssetIngestionService = Depends(get_asset_ingestion_service),
    state_repository: FacilityCovenantStateRepository = Depends(
        get_covenant_state_repository
    ),
) -> IngestAssetsUseCase:
    return IngestAssetsUseCase(
        ingestion_service=ingestion_service,
        state_repository=state_repository,
    )
