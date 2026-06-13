import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.application.registry import FacilityRegistry
from app.domain.calculations.educa import EducaCalculator
from app.domain.calculations.nomina import NominaCalculator
from app.domain.calculations.payearly import PayEarlyCalculator
from app.infrastructure.database.base import Base
from app.infrastructure.publishers.database_publisher import DatabasePublisher
from app.infrastructure.repositories.postgres_asset_repository import (
    PostgresAssetRepository,
)
from app.infrastructure.repositories.postgres_covenant_report_repository import (
    PostgresCovenantReportRepository,
)
from app.main import app
from app.interfaces.api import dependencies

TEST_DB_URL = "sqlite:///./test.db"


@pytest.fixture(scope="session")
def test_engine():
    engine = create_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    if os.path.exists("test.db"):
        os.remove("test.db")


@pytest.fixture
def db_session(test_engine):
    TestSession = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)
    session = TestSession()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@pytest.fixture
def repository(db_session):
    return PostgresCovenantReportRepository(db_session)


@pytest.fixture
def registry():
    reg = FacilityRegistry()
    reg.register("facility-a", EducaCalculator())
    reg.register("facility-b", PayEarlyCalculator())
    reg.register("facility-c", NominaCalculator())
    return reg


@pytest.fixture
def publisher(repository):
    return DatabasePublisher()


@pytest.fixture
def asset_repository(db_session):
    return PostgresAssetRepository(db_session)


@pytest.fixture
def api_client(db_session, registry):
    def override_db():
        yield db_session

    def override_registry():
        return registry

    app.dependency_overrides[dependencies.get_db_session] = override_db
    app.dependency_overrides[dependencies.get_registry] = override_registry

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
def educa_assets():
    path = Path(__file__).parent.parent / "data" / "facility_a_educa_isa.json"
    return json.loads(path.read_text())["assets"]


@pytest.fixture
def payearly_assets():
    path = Path(__file__).parent.parent / "data" / "facility_b_payearly_ewa.json"
    return json.loads(path.read_text())["assets"]


@pytest.fixture
def nomina_assets():
    path = Path(__file__).parent.parent / "data" / "facility_c_nomina.json"
    return json.loads(path.read_text())["assets"]
