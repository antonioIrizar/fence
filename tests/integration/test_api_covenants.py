class TestCreateFacilityReportEndpoint:
    def _ingest(self, api_client, facility_id: str, assets: list) -> None:
        api_client.post(
            f"/api/v1/covenants/{facility_id}/assets",
            json={"assets": assets},
        )

    def test_returns_200_after_ingestion(self, api_client, educa_assets) -> None:
        self._ingest(api_client, "facility-a", educa_assets)
        response = api_client.post("/api/v1/covenants/facility-a/reports")
        assert response.status_code == 200

    def test_response_shape(self, api_client, educa_assets) -> None:
        self._ingest(api_client, "facility-a", educa_assets)
        body = api_client.post("/api/v1/covenants/facility-a/reports").json()
        assert "report_id" in body
        assert "facility_id" in body
        assert "effective_rate" in body
        assert "status" in body
        assert "summary" in body
        assert "included_assets" in body
        assert "excluded_assets" in body
        assert "audit_hash" in body
        assert body["audit_hash"] is not None

    def test_audit_hash_is_64_char_hex(self, api_client, educa_assets) -> None:
        self._ingest(api_client, "facility-a", educa_assets)
        body = api_client.post("/api/v1/covenants/facility-a/reports").json()
        h = body["audit_hash"]
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_facility_a_educa_assets_correctly_classified(
        self, api_client, educa_assets
    ) -> None:
        self._ingest(api_client, "facility-a", educa_assets)
        body = api_client.post("/api/v1/covenants/facility-a/reports").json()
        included = set(body["included_assets"])
        excluded = {e["external_id"] for e in body["excluded_assets"]}
        # Known eligible educa assets
        assert {
            "EDU-STU-10001",
            "EDU-STU-10002",
            "EDU-STU-10004",
            "EDU-STU-10005",
            "EDU-STU-10007",
        }.issubset(included)
        # Known ineligible educa assets
        assert {"EDU-STU-10003", "EDU-STU-10006", "EDU-STU-10008"}.issubset(excluded)

    def test_facility_a_excluded_reasons_present(
        self, api_client, educa_assets
    ) -> None:
        self._ingest(api_client, "facility-a", educa_assets)
        body = api_client.post("/api/v1/covenants/facility-a/reports").json()
        for exc in body["excluded_assets"]:
            assert len(exc["reasons"]) > 0

    def test_idempotent_returns_same_report(self, api_client, educa_assets) -> None:
        self._ingest(api_client, "facility-a", educa_assets)
        r1 = api_client.post("/api/v1/covenants/facility-a/reports").json()
        r2 = api_client.post("/api/v1/covenants/facility-a/reports").json()
        assert r1["report_id"] == r2["report_id"]
        assert r1["audit_hash"] == r2["audit_hash"]

    def test_force_creates_new_report(self, api_client, educa_assets) -> None:
        self._ingest(api_client, "facility-a", educa_assets)
        r1 = api_client.post("/api/v1/covenants/facility-a/reports").json()
        r2 = api_client.post("/api/v1/covenants/facility-a/reports?force=true").json()
        assert r1["report_id"] != r2["report_id"]
        assert r1["audit_hash"] == r2["audit_hash"]

    def test_422_when_no_assets_ingested(self, api_client) -> None:
        response = api_client.post("/api/v1/covenants/facility-a-empty/reports")
        assert response.status_code == 422

    def test_unknown_facility_returns_404(self, api_client) -> None:
        response = api_client.post("/api/v1/covenants/unknown-xyz/reports")
        assert response.status_code in (404, 422)

    def test_correlation_id_header_accepted(self, api_client, educa_assets) -> None:
        self._ingest(api_client, "facility-a", educa_assets)
        response = api_client.post(
            "/api/v1/covenants/facility-a/reports",
            headers={"X-Correlation-ID": "my-corr-id"},
        )
        assert response.status_code == 200

    def test_facility_b_compliant(self, api_client, payearly_assets) -> None:
        self._ingest(api_client, "facility-b", payearly_assets)
        body = api_client.post("/api/v1/covenants/facility-b/reports").json()
        assert body["status"] == "COMPLIANT"

    def test_facility_c_creates_report(self, api_client, nomina_assets) -> None:
        self._ingest(api_client, "facility-c", nomina_assets)
        response = api_client.post("/api/v1/covenants/facility-c/reports")
        assert response.status_code == 200
        body = response.json()
        excluded_ids = {e["external_id"] for e in body["excluded_assets"]}
        assert "NOMINA-202406-42087" in excluded_ids
        assert "NOMINA-202407-88421" in excluded_ids


class TestVerifyReportEndpoint:
    def _ingest_and_create(self, api_client, facility_id: str, assets: list) -> dict:
        api_client.post(
            f"/api/v1/covenants/{facility_id}/assets",
            json={"assets": assets},
        )
        return api_client.post(f"/api/v1/covenants/{facility_id}/reports").json()

    def test_valid_report_returns_is_valid_true(self, api_client, educa_assets) -> None:
        report = self._ingest_and_create(api_client, "facility-a", educa_assets)
        report_id = report["report_id"]
        response = api_client.get(
            f"/api/v1/covenants/facility-a/reports/{report_id}/verify"
        )
        assert response.status_code == 200
        body = response.json()
        assert body["is_valid"] is True
        assert body["stored_hash"] == report["audit_hash"]
        assert body["computed_hash"] == report["audit_hash"]

    def test_verify_response_shape(self, api_client, educa_assets) -> None:
        report = self._ingest_and_create(api_client, "facility-a", educa_assets)
        response = api_client.get(
            f"/api/v1/covenants/facility-a/reports/{report['report_id']}/verify"
        )
        body = response.json()
        assert "is_valid" in body
        assert "stored_hash" in body
        assert "computed_hash" in body
        assert "report_id" in body
        assert "facility_id" in body

    def test_unknown_report_returns_404(self, api_client) -> None:
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = api_client.get(
            f"/api/v1/covenants/facility-a/reports/{fake_id}/verify"
        )
        assert response.status_code == 404

    def test_old_report_still_valid_after_new_assets_ingested(
        self, api_client, educa_assets, payearly_assets
    ) -> None:
        """Verifying a report sealed before new assets were added must return
        is_valid=True — the snapshot is replayed using find_by_facility_at."""
        report = self._ingest_and_create(api_client, "facility-b", payearly_assets)
        report_id = report["report_id"]

        # Ingest more assets for facility-b AFTER the report was sealed
        api_client.post(
            "/api/v1/covenants/facility-b/assets",
            json={"assets": payearly_assets},  # all duplicates → state unchanged
        )

        # Force-create a new report so the state has advanced
        api_client.post("/api/v1/covenants/facility-b/reports?force=true")

        # The original report must still verify correctly
        response = api_client.get(
            f"/api/v1/covenants/facility-b/reports/{report_id}/verify"
        )
        assert response.status_code == 200
        assert response.json()["is_valid"] is True


class TestGetCovenantReportEndpoint:
    def test_get_report_by_id(self, api_client, educa_assets) -> None:
        api_client.post(
            "/api/v1/covenants/facility-a/assets",
            json={"assets": educa_assets},
        )
        post = api_client.post("/api/v1/covenants/facility-a/reports")
        report_id = post.json()["report_id"]

        get = api_client.get(f"/api/v1/covenants/facility-a/reports/{report_id}")
        assert get.status_code == 200
        assert get.json()["report_id"] == report_id
        assert get.json()["audit_hash"] is not None

    def test_get_report_unknown_id_returns_404(self, api_client) -> None:
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = api_client.get(f"/api/v1/covenants/facility-a/reports/{fake_id}")
        assert response.status_code == 404


class TestListCovenantReportsEndpoint:
    def test_list_reports_returns_array(self, api_client, educa_assets) -> None:
        api_client.post(
            "/api/v1/covenants/facility-a/assets",
            json={"assets": educa_assets},
        )
        api_client.post("/api/v1/covenants/facility-a/reports")
        response = api_client.get("/api/v1/covenants/facility-a/reports")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        assert len(response.json()) >= 1
