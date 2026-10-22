"""Opt-in SQL tests. Only a dedicated temporary Unix-socket database is allowed."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
import os
import uuid

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict
import pytest

import service_api
from test_service_api import API_KEY, valid_payload


@pytest.fixture
def database(monkeypatch):
    dsn = os.environ.get("CONTROL_TOWER_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("Set CONTROL_TOWER_TEST_DATABASE_URL for isolated SQL tests")
    settings = conninfo_to_dict(dsn)
    local_socket = settings.get("host", "").startswith("/private/tmp/ct-approval-test-")
    ci_service = (os.environ.get("GITHUB_ACTIONS") == "true"
                  and settings.get("host") == "127.0.0.1")
    if settings.get("dbname") != "ct_approval_test" or not (local_socket or ci_service):
        pytest.fail("SQL tests require a dedicated temporary Unix-socket database")

    real_connect = psycopg.connect
    schema = "approval_" + uuid.uuid4().hex
    with real_connect(dsn, autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))

    def connect(*args, **kwargs):
        return real_connect(dsn, options=f"-c search_path={schema}")

    with connect() as connection:
        connection.execute(Path(__file__).with_name("init.sql").read_text())

    monkeypatch.setattr(service_api.psycopg, "connect", connect)
    monkeypatch.setattr(service_api, "EXPECTED_API_KEY", API_KEY)
    monkeypatch.setitem(service_api.app.config, "TESTING", True)
    try:
        yield connect
    finally:
        with real_connect(dsn, autocommit=True) as connection:
            # Only this test's newly created, randomly named schema is removed.
            connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


def intake(monkeypatch, urgency="High", warranty=True):
    monkeypatch.setattr(service_api, "classify_case", lambda *args: {
        "issue_category": "Battery",
        "affected_system": "Battery",
        "urgency": urgency,
        "summary": "Synthetic SQL regression case",
        "technician_skill": "EV high-voltage technician",
        "required_parts": ["BMS"]
    })
    payload = valid_payload()
    payload["case_id"] = "sql-test-" + uuid.uuid4().hex
    payload["warranty_active"] = warranty
    response = service_api.app.test_client().post(
        "/service-cases", json=payload, headers={"X-API-Key": API_KEY}
    )
    assert response.status_code == 200
    return payload["case_id"]


def action(case_id, route, decision="approved"):
    return service_api.app.test_client().open(
        f"/service-cases/{case_id}/{route}",
        method="GET" if route == "resources" else "POST",
        headers={"X-API-Key": API_KEY},
        json={"decision": decision, "reviewer": "synthetic-reviewer"}
    )


def scalar(database, query, params=None):
    with database() as connection:
        return connection.execute(query, params).fetchone()[0]


@pytest.mark.parametrize("route", ["resources", "appointment"])
@pytest.mark.parametrize("reject", [False, True])
def test_sql_pending_and_rejected_block(monkeypatch, database, route, reject):
    case_id = intake(monkeypatch)
    if reject:
        assert action(case_id, "approval", "rejected").status_code == 200
        assert scalar(database, "SELECT requires_human_review FROM service_cases") is False

    response = action(case_id, route)
    assert response.status_code == 409
    assert response.get_json()["status"] == ("rejected" if reject else "awaiting_review")
    assert scalar(database, "SELECT COUNT(*) FROM appointments") == 0
    assert scalar(database, "SELECT matched_technician_id FROM service_cases") is None


@pytest.mark.parametrize("urgency,warranty", [
    ("Critical", True), ("High", False), ("Low", True), ("Low", False)
])
def test_sql_actionable_workflow(monkeypatch, database, urgency, warranty):
    case_id = intake(monkeypatch, urgency, warranty)
    requires_review = urgency in {"High", "Critical"} or warranty
    if requires_review:
        assert action(case_id, "appointment").status_code == 409
        assert action(case_id, "approval").status_code == 200
    assert action(case_id, "resources").get_json()["resources_ready"] is True
    assert action(case_id, "appointment").status_code == 200
    assert scalar(database, "SELECT COUNT(*) FROM appointments") == 1
    assert scalar(database, "SELECT COUNT(*) FROM audit_events") == int(requires_review)
    duplicate = action(case_id, "appointment")
    assert duplicate.get_json()["duplicate"] is True
    assert scalar(database, "SELECT COUNT(*) FROM appointments") == 1


@pytest.mark.parametrize("resource", ["parts", "technician"])
def test_sql_rechecks_changed_resources(monkeypatch, database, resource):
    case_id = intake(monkeypatch)
    assert action(case_id, "approval").status_code == 200
    assert action(case_id, "resources").get_json()["resources_ready"] is True
    with database() as connection:
        if resource == "parts":
            connection.execute("UPDATE parts_inventory SET stock_quantity = 0")
        else:
            connection.execute("UPDATE technicians SET availability_status = 'busy'")
    assert action(case_id, "appointment").status_code == 409
    assert scalar(database, "SELECT COUNT(*) FROM appointments") == 0


def test_sql_approval_audit_failure_rolls_back(monkeypatch, database):
    case_id = intake(monkeypatch)
    with database() as connection:
        connection.execute("ALTER TABLE audit_events ADD CONSTRAINT test_fail CHECK (FALSE)")
    with pytest.raises(psycopg.errors.CheckViolation):
        action(case_id, "approval")
    assert scalar(database, "SELECT status FROM service_cases") == "awaiting_review"
    assert scalar(database, "SELECT requires_human_review FROM service_cases") is True
    assert scalar(database, "SELECT COUNT(*) FROM audit_events") == 0


def test_sql_concurrent_decisions_only_one_wins(monkeypatch, database):
    case_id = intake(monkeypatch)
    start = Barrier(2)

    def decide(decision):
        start.wait(timeout=10)
        return action(case_id, "approval", decision).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(decide, d) for d in ["approved", "rejected"]]
        assert sorted(f.result(timeout=15) for f in futures) == [200, 409]
    assert scalar(database, "SELECT COUNT(*) FROM audit_events") == 1
    with database() as connection:
        state = connection.execute("SELECT status, requires_human_review FROM service_cases").fetchone()
        event = connection.execute("SELECT event_type FROM audit_events").fetchone()[0]
    assert state[1] is False
    assert event == f"warranty_{state[0]}"


def test_sql_concurrent_proposals_create_one_row(monkeypatch, database):
    case_id = intake(monkeypatch)
    assert action(case_id, "approval").status_code == 200
    assert action(case_id, "resources").get_json()["resources_ready"] is True
    start = Barrier(2)

    def propose():
        start.wait(timeout=10)
        response = action(case_id, "appointment")
        assert response.status_code == 200
        return response.get_json()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(propose) for _ in range(2)]
        results = [f.result(timeout=15) for f in futures]
    assert sum(bool(r.get("duplicate")) for r in results) == 1
    assert scalar(database, "SELECT COUNT(*) FROM appointments") == 1


def test_sql_concurrent_intake_creates_one_case(monkeypatch, database):
    monkeypatch.setattr(service_api, "classify_case", lambda *args: {
        "issue_category": "Infotainment",
        "affected_system": "Display",
        "urgency": "Low",
        "summary": "Synthetic concurrent intake",
        "technician_skill": "Infotainment technician",
        "required_parts": []
    })
    payload = valid_payload()
    payload["case_id"] = "concurrent-intake-" + uuid.uuid4().hex
    start = Barrier(2)

    def submit():
        start.wait(timeout=10)
        response = service_api.app.test_client().post(
            "/service-cases", json=payload, headers={"X-API-Key": API_KEY}
        )
        assert response.status_code == 200
        return response.get_json()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(submit), executor.submit(submit)]
        results = [future.result(timeout=15) for future in futures]

    assert sum(bool(result.get("duplicate")) for result in results) == 1
    assert scalar(database, "SELECT COUNT(*) FROM service_cases") == 1
