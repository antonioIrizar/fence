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


def test_ingest_assets_new(api_client) -> None:
    body = {"assets": [_educa_raw("NEW-001"), _educa_raw("NEW-002")]}
    resp = api_client.post("/api/v1/covenants/facility-a/assets", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert set(data["saved"]) == {"NEW-001", "NEW-002"}
    assert data["duplicates"] == []
    assert data["saved_count"] == 2
    assert data["duplicate_count"] == 0


def test_ingest_assets_with_duplicates(api_client) -> None:
    body = {"assets": [_educa_raw("DUP-001")]}
    api_client.post("/api/v1/covenants/facility-a/assets", json=body)

    # Second call with same + new asset
    body2 = {"assets": [_educa_raw("DUP-001"), _educa_raw("DUP-NEW-001")]}
    resp = api_client.post("/api/v1/covenants/facility-a/assets", json=body2)
    assert resp.status_code == 200
    data = resp.json()
    assert data["saved"] == ["DUP-NEW-001"]
    assert data["duplicates"] == ["DUP-001"]
    assert data["saved_count"] == 1
    assert data["duplicate_count"] == 1


def test_ingest_assets_all_duplicates(api_client) -> None:
    body = {"assets": [_educa_raw("ALLDUPE-001")]}
    api_client.post("/api/v1/covenants/facility-a/assets", json=body)

    resp = api_client.post("/api/v1/covenants/facility-a/assets", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert data["saved"] == []
    assert data["duplicates"] == ["ALLDUPE-001"]
    assert data["saved_count"] == 0
    assert data["duplicate_count"] == 1


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
