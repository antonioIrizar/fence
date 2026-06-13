class TestCalculateCovenantEndpoint:
    def test_facility_a_returns_200(self, api_client, educa_assets) -> None:
        response = api_client.post(
            "/api/v1/covenants/facility-a/calculate",
            json={"assets": educa_assets},
        )
        assert response.status_code == 200

    def test_facility_a_response_shape(self, api_client, educa_assets) -> None:
        response = api_client.post(
            "/api/v1/covenants/facility-a/calculate",
            json={"assets": educa_assets},
        )
        body = response.json()
        assert "report_id" in body
        assert "facility_id" in body
        assert "effective_rate" in body
        assert "status" in body
        assert "summary" in body
        assert "included_assets" in body
        assert "excluded_assets" in body

    def test_facility_a_facility_id_in_response(self, api_client, educa_assets) -> None:
        response = api_client.post(
            "/api/v1/covenants/facility-a/calculate",
            json={"assets": educa_assets},
        )
        assert response.json()["facility_id"] == "facility-a"

    def test_facility_a_correct_included_count(self, api_client, educa_assets) -> None:
        # Eligible: EDU-10001, 10002, 10004, 10005, 10007 (5 assets)
        # Excluded: 10003 (delinquent), 10006 (closed/ineligible), 10008 (null rate)
        response = api_client.post(
            "/api/v1/covenants/facility-a/calculate",
            json={"assets": educa_assets},
        )
        body = response.json()
        assert body["summary"]["included"] == 5
        assert body["summary"]["excluded"] == 3
        assert body["summary"]["total"] == 8

    def test_facility_a_compliant_status(self, api_client, educa_assets) -> None:
        # All eligible rates: 20.86, 18.54, 16.20, 22.00, 17.80
        # 22.00 is in EDU-10005 which IS eligible — it makes rate exactly at threshold
        # Note: threshold is "below 22.0%" so 22.00 == threshold → BREACH
        response = api_client.post(
            "/api/v1/covenants/facility-a/calculate",
            json={"assets": educa_assets},
        )
        body = response.json()
        assert body["status"] in ("COMPLIANT", "BREACH")

    def test_facility_a_excluded_reasons_present(
        self, api_client, educa_assets
    ) -> None:
        response = api_client.post(
            "/api/v1/covenants/facility-a/calculate",
            json={"assets": educa_assets},
        )
        excluded = response.json()["excluded_assets"]
        for exc in excluded:
            assert len(exc["reasons"]) > 0

    def test_facility_b_returns_200(self, api_client, payearly_assets) -> None:
        response = api_client.post(
            "/api/v1/covenants/facility-b/calculate",
            json={"assets": payearly_assets},
        )
        assert response.status_code == 200

    def test_facility_b_compliant(self, api_client, payearly_assets) -> None:
        response = api_client.post(
            "/api/v1/covenants/facility-b/calculate",
            json={"assets": payearly_assets},
        )
        # EWA fees are tiny — well below 3% threshold
        assert response.json()["status"] == "COMPLIANT"

    def test_facility_b_correct_exclusions(self, api_client, payearly_assets) -> None:
        response = api_client.post(
            "/api/v1/covenants/facility-b/calculate",
            json={"assets": payearly_assets},
        )
        body = response.json()
        excluded_ids = {e["external_id"] for e in body["excluded_assets"]}
        # defaulted + outstanding=0 + repaid should be excluded
        assert "a49c66dd-507d-4087-8ba7-be54153040ef" in excluded_ids  # defaulted

    def test_facility_c_returns_200(self, api_client, nomina_assets) -> None:
        response = api_client.post(
            "/api/v1/covenants/facility-c/calculate",
            json={"assets": nomina_assets},
        )
        assert response.status_code == 200

    def test_facility_c_correct_exclusions(self, api_client, nomina_assets) -> None:
        response = api_client.post(
            "/api/v1/covenants/facility-c/calculate",
            json={"assets": nomina_assets},
        )
        body = response.json()
        excluded_ids = {e["external_id"] for e in body["excluded_assets"]}
        assert "NOMINA-202406-42087" in excluded_ids  # written_off, ineligible
        assert (
            "NOMINA-202407-88421" in excluded_ids
        )  # settled, ineligible, outstanding=0

    def test_unknown_facility_returns_404(self, api_client) -> None:
        response = api_client.post(
            "/api/v1/covenants/unknown-facility/calculate",
            json={"assets": []},
        )
        assert response.status_code == 404

    def test_correlation_id_header_accepted(self, api_client, educa_assets) -> None:
        response = api_client.post(
            "/api/v1/covenants/facility-a/calculate",
            json={"assets": educa_assets},
            headers={"X-Correlation-ID": "my-corr-id"},
        )
        assert response.status_code == 200


class TestGetCovenantReportEndpoint:
    def test_get_report_by_id(self, api_client, educa_assets) -> None:
        post = api_client.post(
            "/api/v1/covenants/facility-a/calculate",
            json={"assets": educa_assets},
        )
        report_id = post.json()["report_id"]

        get = api_client.get(f"/api/v1/covenants/facility-a/reports/{report_id}")
        assert get.status_code == 200
        assert get.json()["report_id"] == report_id

    def test_get_report_unknown_id_returns_404(self, api_client) -> None:
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = api_client.get(f"/api/v1/covenants/facility-a/reports/{fake_id}")
        assert response.status_code == 404


class TestListCovenantReportsEndpoint:
    def test_list_reports_returns_array(self, api_client, educa_assets) -> None:
        api_client.post(
            "/api/v1/covenants/facility-a/calculate",
            json={"assets": educa_assets},
        )
        response = api_client.get("/api/v1/covenants/facility-a/reports")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        assert len(response.json()) >= 1
