"""Integration tests for the asset ingestion endpoint."""

from typing import Any


def _educa_raw(external_id: str) -> dict[str, Any]:
    return {
        "external_id": external_id,
        "status": "open",
        "amount": "10000.00",
        "is_eligible": True,
        "loan_status": "current",
        "outstanding_amount": "9500.00",
        "interest_rate_percentage": "18.5",
        "effective_date": "2024-01-01",
        "reporting_date": "2024-06-01",
        "student_id": "STU-001",
        "school_id": "SCH-001",
        "disbursement_amount": "10000.00",
        "repaid_amount": "500.00",
        "days_past_due": 0,
        "country": "ES",
    }


def _assert_covenant_state(data: dict) -> None:
    cs = data["covenant_state"]
    assert "facility_id" in cs
    assert "effective_rate" in cs
    assert "covenant_status" in cs
    assert "accumulated_numerator" in cs
    assert "accumulated_denominator" in cs
    assert "last_updated" in cs


def test_ingest_assets_new(api_client) -> None:
    body = {"assets": [_educa_raw("API-NEW-001"), _educa_raw("API-NEW-002")]}
    resp = api_client.post("/api/v1/covenants/facility-a/assets", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert set(data["saved"]) == {"API-NEW-001", "API-NEW-002"}
    assert data["duplicates"] == []
    assert data["saved_count"] == 2
    assert data["duplicate_count"] == 0
    _assert_covenant_state(data)
    assert data["covenant_state"]["covenant_status"] == "COMPLIANT"


def test_ingest_assets_with_duplicates(api_client) -> None:
    body = {"assets": [_educa_raw("API-DUP-001")]}
    api_client.post("/api/v1/covenants/facility-a/assets", json=body)

    body2 = {"assets": [_educa_raw("API-DUP-001"), _educa_raw("API-DUP-NEW-001")]}
    resp = api_client.post("/api/v1/covenants/facility-a/assets", json=body2)
    assert resp.status_code == 200
    data = resp.json()
    assert data["saved"] == ["API-DUP-NEW-001"]
    assert data["duplicates"] == ["API-DUP-001"]
    _assert_covenant_state(data)


def test_ingest_assets_all_duplicates(api_client) -> None:
    body = {"assets": [_educa_raw("API-ALLDUPE-001")]}
    api_client.post("/api/v1/covenants/facility-a/assets", json=body)

    resp = api_client.post("/api/v1/covenants/facility-a/assets", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert data["saved"] == []
    assert data["duplicates"] == ["API-ALLDUPE-001"]
    _assert_covenant_state(data)


def test_covenant_state_accumulates_across_calls(api_client) -> None:
    body1 = {"assets": [_educa_raw("API-ACC-001")]}
    r1 = api_client.post("/api/v1/covenants/facility-a/assets", json=body1)
    num1 = float(r1.json()["covenant_state"]["accumulated_numerator"])

    body2 = {"assets": [_educa_raw("API-ACC-002")]}
    r2 = api_client.post("/api/v1/covenants/facility-a/assets", json=body2)
    num2 = float(r2.json()["covenant_state"]["accumulated_numerator"])

    # Second call adds more to the numerator
    assert num2 > num1


def test_ingest_assets_missing_external_id_returns_422(api_client) -> None:
    body = {"assets": [{"status": "open", "amount": "100", "is_eligible": True}]}
    resp = api_client.post("/api/v1/covenants/facility-a/assets", json=body)
    assert resp.status_code == 422


def test_ingest_assets_empty_list_returns_empty(api_client) -> None:
    resp = api_client.post("/api/v1/covenants/facility-a/assets", json={"assets": []})
    assert resp.status_code == 200
    data = resp.json()
    assert data["saved"] == []
    assert data["duplicates"] == []
    _assert_covenant_state(data)


def test_asset_record_stores_eligibility_info(api_client, db_session) -> None:
    from app.infrastructure.repositories.postgres_asset_repository import (
        PostgresAssetRepository,
    )

    body = {"assets": [_educa_raw("API-ELIG-001")]}
    api_client.post("/api/v1/covenants/facility-a/assets", json=body)

    repo = PostgresAssetRepository(db_session)
    records = repo.find_by_facility("facility-a")
    record = next(r for r in records if r.external_id == "API-ELIG-001")

    assert record.is_eligible_asset is True
    assert record.exclusion_reasons == []
    assert record.contribution_numerator is not None
    assert record.contribution_denominator is not None
