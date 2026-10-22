import service_api
import pytest


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


class ScriptedDatabase:
    """Record SQL and return explicit fixtures; never contact a database."""

    def __init__(self, rows, technicians=()):
        self.rows = iter(rows)
        self.technicians = technicians
        self.queries = []
        self.commits = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        return self

    def execute(self, query, params=None):
        self.queries.append((" ".join(query.split()), params))

    def fetchone(self):
        return next(self.rows)

    def fetchall(self):
        return self.technicians

    def commit(self):
        self.commits += 1


def use_database(monkeypatch, rows, technicians=()):
    configure_api(monkeypatch)
    database = ScriptedDatabase(rows, technicians)
    monkeypatch.setattr(service_api.psycopg, "connect", lambda _: database)
    return database


def downstream_request(route):
    client = service_api.app.test_client()
    return client.open(
        f"/service-cases/test-case-001/{route}",
        method="GET" if route == "resources" else "POST",
        headers={"X-API-Key": API_KEY}
    )


@pytest.mark.parametrize("route", ["resources", "appointment"])
@pytest.mark.parametrize("state", [
    ("awaiting_review", True, "Critical", True, "requires_review"),
    ("rejected", False, "Critical", True, "rejected"),
    ("classified", False, "Critical", False, "not_eligible"),
    ("classified", False, "High", False, "not_eligible"),
    ("classified", False, "Low", True, "requires_review"),
    ("approved", True, "High", False, "approved"),
    ("awaiting_review", False, "Low", False, "not_eligible"),
    ("classified", False, "Low", False, "rejected"),
    ("unexpected", False, "Low", False, "not_eligible"),
    ("classified", None, "Low", False, "not_eligible"),
    ("approved", False, "unexpected", False, "approved"),
])
def test_downstream_blocks_without_mutation(monkeypatch, route, state):
    status, pending, urgency, warranty, warranty_status = state
    if route == "resources":
        row = ("Infotainment technician", [], *state)
    else:
        row = (2, True, urgency, status, pending, warranty, warranty_status, [])
    database = use_database(monkeypatch, [row])

    response = downstream_request(route)

    assert response.status_code == 409
    assert response.get_json()["received"] is False
    # No resource lookup, case write, appointment insert or commit.
    assert len(database.queries) == 1
    assert "FOR UPDATE" in database.queries[0][0]
    assert database.commits == 0


@pytest.mark.parametrize("route", ["resources", "appointment"])
def test_downstream_missing_case(monkeypatch, route):
    database = use_database(monkeypatch, [None])
    assert downstream_request(route).status_code == 404
    assert database.commits == 0


@pytest.mark.parametrize("route", ["resources", "appointment", "approval"])
def test_downstream_requires_key_before_database(monkeypatch, route):
    configure_api(monkeypatch)

    def unexpected_connection(*args, **kwargs):
        pytest.fail("Unauthenticated request contacted the database")

    monkeypatch.setattr(service_api.psycopg, "connect", unexpected_connection)
    client = service_api.app.test_client()
    response = client.open(
        f"/service-cases/test-case-001/{route}",
        method="GET" if route == "resources" else "POST"
    )
    assert response.status_code == 401


@pytest.mark.parametrize("status,urgency,warranty", [
    ("classified", "Low", False),
    ("approved", "Critical", True),
])
def test_actionable_cases_match_resources(monkeypatch, status, urgency, warranty):
    row = ("Infotainment technician", [], status, False, urgency, warranty,
           "approved" if status == "approved" else "not_eligible")
    database = use_database(monkeypatch, [row], technicians=[
        (2, "Demo Technician", "Infotainment technician", "available", "Demo")
    ])
    response = downstream_request("resources")
    assert response.status_code == 200
    assert response.get_json()["resources_ready"] is True
    assert database.commits == 1


@pytest.mark.parametrize("status,urgency,warranty", [
    ("classified", "Low", False),
    ("approved", "Critical", True),
])
def test_actionable_cases_propose_appointment(monkeypatch, status, urgency, warranty):
    row = (2, True, urgency, status, False, warranty,
           "approved" if status == "approved" else "not_eligible", ["BMS"])
    database = use_database(monkeypatch, [
        row, (2, "Demo Technician", "Demo"), ("BMS", 3, "Demo"), (101,)
    ])
    response = downstream_request("appointment")
    assert response.status_code == 200
    assert response.get_json()["appointment_id"] == 101
    assert database.commits == 1
    assert any("availability_status = 'available'" in q for q, _ in database.queries)
    assert any("parts_inventory" in q and "FOR SHARE" in q
               for q, _ in database.queries)


@pytest.mark.parametrize("technician,parts", [(None, True), (2, False)])
def test_missing_recorded_resources_block_appointment(monkeypatch, technician, parts):
    database = use_database(monkeypatch, [
        (technician, parts, "High", "approved", False, True, "approved", [])
    ])
    assert downstream_request("appointment").status_code == 409
    assert len(database.queries) == 1
    assert database.commits == 0


@pytest.mark.parametrize("missing_part", [None, ("BMS", 0, "Demo")])
def test_inventory_rechecked_before_appointment(monkeypatch, missing_part):
    database = use_database(monkeypatch, [
        (2, True, "High", "approved", False, True, "approved", ["BMS"]),
        (2, "Demo Technician", "Demo"), missing_part
    ])
    response = downstream_request("appointment")
    assert response.status_code == 409
    assert response.get_json()["status"] == "resource_review"
    assert not any("INSERT" in q for q, _ in database.queries)
    assert database.commits == 0


def test_unavailable_technician_blocks_appointment(monkeypatch):
    database = use_database(monkeypatch, [
        (2, True, "High", "approved", False, True, "approved", []), None
    ])
    assert downstream_request("appointment").status_code == 409
    assert not any("INSERT" in q for q, _ in database.queries)
    assert database.commits == 0


def test_duplicate_appointment_is_not_committed(monkeypatch):
    database = use_database(monkeypatch, [
        (2, True, "Low", "classified", False, False, "not_eligible", []),
        (2, "Demo Technician", "Demo"), None
    ])
    response = downstream_request("appointment")
    assert response.status_code == 200
    assert response.get_json()["duplicate"] is True
    assert database.commits == 0


@pytest.mark.parametrize("decision", ["approved", "rejected"])
def test_pending_case_decision_and_audit_are_atomic(monkeypatch, decision):
    database = use_database(monkeypatch, [(True, "awaiting_review")])
    response = service_api.app.test_client().post(
        "/service-cases/test-case-001/approval",
        headers={"X-API-Key": API_KEY},
        json={"decision": decision, "reviewer": "demo-reviewer"}
    )
    assert response.status_code == 200
    assert response.get_json()["status"] == decision
    assert "FOR UPDATE" in database.queries[0][0]
    assert any("UPDATE service_cases" in q for q, _ in database.queries)
    assert any("INSERT INTO audit_events" in q for q, _ in database.queries)
    assert database.commits == 1


@pytest.mark.parametrize("row", [
    (False, "approved"), (False, "rejected"), (False, "classified"),
    (True, "approved"), (True, "rejected"), (False, "awaiting_review")
])
def test_repeated_or_inconsistent_decision_is_blocked(monkeypatch, row):
    database = use_database(monkeypatch, [row])
    response = service_api.app.test_client().post(
        "/service-cases/test-case-001/approval",
        headers={"X-API-Key": API_KEY},
        json={"decision": "approved", "reviewer": "demo-reviewer"}
    )
    assert response.status_code == 409
    assert len(database.queries) == 1
    assert database.commits == 0
