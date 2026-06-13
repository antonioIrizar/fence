"""Tests for API exception handlers."""

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.domain.errors import (
    CovenantCalculationError,
    CovenantPublicationError,
    InvalidPortfolioData,
)
from app.interfaces.api import dependencies
from app.main import app


def _make_client_with_use_case_raising(exc):
    mock_uc = MagicMock()
    mock_uc.execute.side_effect = exc

    def override_db():
        yield MagicMock()

    def override_use_case(**_):
        return mock_uc

    app.dependency_overrides[dependencies.get_db_session] = override_db
    app.dependency_overrides[dependencies.get_calculate_use_case] = lambda: mock_uc
    client = TestClient(app, raise_server_exceptions=False)
    return client


class TestExceptionHandlers:
    def teardown_method(self) -> None:
        app.dependency_overrides.clear()

    def test_invalid_portfolio_data_returns_422(self) -> None:
        client = _make_client_with_use_case_raising(InvalidPortfolioData("bad field"))
        resp = client.post(
            "/api/v1/covenants/facility-a/calculate",
            json={"assets": []},
        )
        assert resp.status_code == 422
        assert "bad field" in resp.json()["detail"]

    def test_covenant_calculation_error_returns_500(self) -> None:
        client = _make_client_with_use_case_raising(
            CovenantCalculationError("no eligible assets")
        )
        resp = client.post(
            "/api/v1/covenants/facility-a/calculate",
            json={"assets": []},
        )
        assert resp.status_code == 500

    def test_covenant_publication_error_returns_500(self) -> None:
        client = _make_client_with_use_case_raising(CovenantPublicationError("db down"))
        resp = client.post(
            "/api/v1/covenants/facility-a/calculate",
            json={"assets": []},
        )
        assert resp.status_code == 500
