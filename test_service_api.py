import service_api


API_KEY = "control-tower-demo-key-2026"


def valid_payload():
    return {
        "case_id": "test-case-001",
        "customer_name": "Test User",
        "customer_email": "test@example.com",
        "vehicle_make": "Hyundai",
        "vehicle_model": "Kona Electric",
        "vehicle_year": 2023,
        "vin": "TEST123456",
        "symptom_description": (
            "The infotainment screen freezes occasionally."
        ),
        "warranty_active": False
    }


def configure_api(monkeypatch):
    monkeypatch.setattr(
        service_api,
        "EXPECTED_API_KEY",
        API_KEY
    )


def test_missing_api_key_is_rejected(monkeypatch):
    configure_api(monkeypatch)

    client = service_api.app.test_client()
    response = client.post(
        "/service-cases",
        json=valid_payload()
    )

    assert response.status_code == 401
    assert response.get_json()["error"] == "Unauthorized"


def test_missing_required_field_is_rejected(monkeypatch):
    configure_api(monkeypatch)

    client = service_api.app.test_client()
    payload = valid_payload()
    payload.pop("customer_email")

    response = client.post(
        "/service-cases",
        json=payload,
        headers={"X-API-Key": API_KEY}
    )

    assert response.status_code == 400
    assert response.get_json()["status"] == "invalid"


def test_duplicate_case_is_rejected(monkeypatch):
    configure_api(monkeypatch)

    monkeypatch.setattr(
        service_api,
        "case_already_exists",
        lambda case_id: True
    )

    client = service_api.app.test_client()
    response = client.post(
        "/service-cases",
        json=valid_payload(),
        headers={"X-API-Key": API_KEY}
    )

    body = response.get_json()

    assert response.status_code == 200
    assert body["duplicate"] is True
    assert body["received"] is False


def test_low_risk_case_is_saved(monkeypatch):
    configure_api(monkeypatch)

    monkeypatch.setattr(
        service_api,
        "case_already_exists",
        lambda case_id: False
    )

    monkeypatch.setattr(
        service_api,
        "classify_case",
        lambda symptom, warranty: {
            "issue_category": "Infotainment",
            "affected_system": "Center display",
            "urgency": "Low",
            "summary": "Intermittent infotainment freezing",
            "technician_skill": "Infotainment technician",
            "required_parts": []
        }
    )

    monkeypatch.setattr(
        service_api,
        "save_case",
        lambda case: 101
    )

    client = service_api.app.test_client()
    response = client.post(
        "/service-cases",
        json=valid_payload(),
        headers={"X-API-Key": API_KEY}
    )

    body = response.get_json()

    assert response.status_code == 200
    assert body["received"] is True
    assert body["saved"] is True
    assert body["database_id"] == 101
    assert body["case"]["status"] == "classified"
    assert body["case"]["requires_human_review"] is False


def test_high_risk_case_requires_review(monkeypatch):
    configure_api(monkeypatch)

    monkeypatch.setattr(
        service_api,
        "case_already_exists",
        lambda case_id: False
    )

    monkeypatch.setattr(
        service_api,
        "classify_case",
        lambda symptom, warranty: {
            "issue_category": "Battery",
            "affected_system": "High-voltage battery",
            "urgency": "Critical",
            "summary": "Battery warning with loss of propulsion",
            "technician_skill": "Certified EV battery technician",
            "required_parts": ["BMS module"]
        }
    )

    monkeypatch.setattr(
        service_api,
        "save_case",
        lambda case: 102
    )

    client = service_api.app.test_client()
    payload = valid_payload()
    payload["warranty_active"] = True

    response = client.post(
        "/service-cases",
        json=payload,
        headers={"X-API-Key": API_KEY}
    )

    body = response.get_json()

    assert response.status_code == 200
    assert body["case"]["status"] == "awaiting_review"
    assert body["case"]["requires_human_review"] is True


def test_ai_failure_routes_to_human_review(monkeypatch):
    configure_api(monkeypatch)

    monkeypatch.setattr(
        service_api,
        "case_already_exists",
        lambda case_id: False
    )

    def failed_classification(symptom, warranty):
        raise RuntimeError("Mock AI failure")

    monkeypatch.setattr(
        service_api,
        "classify_case",
        failed_classification
    )

    client = service_api.app.test_client()
    response = client.post(
        "/service-cases",
        json=valid_payload(),
        headers={"X-API-Key": API_KEY}
    )

    body = response.get_json()

    assert response.status_code == 422
    assert body["status"] == "human_review"
    assert body["received"] is False
