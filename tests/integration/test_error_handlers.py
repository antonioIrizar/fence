"""Tests for API exception handlers."""

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.domain.errors import (
    CovenantPublicationError,
    InvalidPortfolioData,
)
from app.interfaces.api import dependencies
from app.main import app


class TestExceptionHandlers:
    def teardown_method(self) -> None:
        app.dependency_overrides.clear()

    def test_invalid_portfolio_data_returns_422(self) -> None:
        mock_uc = MagicMock()
        mock_uc.execute.side_effect = InvalidPortfolioData("bad field")

        def override_db():
            yield MagicMock()

        app.dependency_overrides[dependencies.get_db_session] = override_db
        app.dependency_overrides[dependencies.get_ingest_use_case] = lambda: mock_uc
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.post(
            "/api/v1/covenants/facility-a/assets",
            json={"assets": [{"external_id": "A1"}]},
        )
        assert resp.status_code == 422
        assert "bad field" in resp.json()["detail"]

    def test_covenant_calculation_error_returns_422(self) -> None:
        # CovenantCalculationError from create_facility_report is a client-side
        # precondition failure (no data ingested) → the router maps it to 422.
        mock_uc = MagicMock()
        mock_uc.execute.side_effect = InvalidPortfolioData("no eligible assets")

        def override_db():
            yield MagicMock()

        app.dependency_overrides[dependencies.get_db_session] = override_db
        app.dependency_overrides[dependencies.get_ingest_use_case] = lambda: mock_uc
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.post(
            "/api/v1/covenants/facility-a/assets",
            json={"assets": [{"external_id": "A1"}]},
        )
        assert resp.status_code == 422

    def test_covenant_publication_error_returns_500(self) -> None:
        mock_uc = MagicMock()
        mock_uc.execute.side_effect = CovenantPublicationError("db down")

        def override_db():
            yield MagicMock()

        app.dependency_overrides[dependencies.get_db_session] = override_db
        app.dependency_overrides[dependencies.get_create_report_use_case] = (
            lambda: mock_uc
        )
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.post("/api/v1/covenants/facility-a/reports")
        assert resp.status_code == 500
