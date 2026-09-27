from flask import Flask, request, jsonify
from openai import OpenAI
import psycopg
import json
import os
import re
import uuid
from datetime import datetime, timezone, timedelta

app = Flask(__name__)

EXPECTED_API_KEY = os.environ.get("SERVICE_API_KEY")
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "dbname=service_ops_db"
)


def classify_case(symptom_description, warranty_active):
    client = OpenAI()

    response = client.responses.create(
        model="gpt-5-mini",
        instructions=(
            "You classify EV service cases. "
            "Return only valid JSON with exactly these fields: "
            "issue_category, affected_system, urgency, summary, "
            "technician_skill, required_parts. "
            "Urgency must be Low, Medium, High, or Critical. "
            "required_parts must be an array of strings. "
            "Do not add extra text."
        ),
        input=(
            f"Warranty active: {warranty_active}\n"
            f"Customer symptom: {symptom_description}"
        )
    )

    result = json.loads(response.output_text)

    required_fields = [
        "issue_category",
        "affected_system",
        "urgency",
        "summary",
        "technician_skill",
        "required_parts"
    ]

    for field in required_fields:
        if field not in result:
            raise ValueError(f"Missing AI field: {field}")

    if result["urgency"] not in ["Low", "Medium", "High", "Critical"]:
        raise ValueError("Invalid urgency returned by AI")

    if not isinstance(result["required_parts"], list):
        raise ValueError("required_parts must be a list")

    return result


def case_already_exists(case_id):
    with psycopg.connect(DATABASE_URL) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM service_cases WHERE case_id = %s",
                (case_id,)
            )
            return cursor.fetchone() is not None


def save_case(case):
    with psycopg.connect(DATABASE_URL) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO service_cases (
                    case_id,
                    customer_name,
                    customer_email,
                    vehicle_make,
                    vehicle_model,
                    vehicle_year,
                    vin,
                    symptom_description,
                    issue_category,
                    affected_system,
                    urgency,
                    ai_summary,
                    technician_skill,
                    required_parts,
                    warranty_active,
                    warranty_status,
                    requires_human_review,
                    status,
                    created_at,
                    updated_at
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                RETURNING id
                """,
                (
                    case["case_id"],
                    case["customer_name"],
                    case["customer_email"],
                    case["vehicle_make"],
                    case["vehicle_model"],
                    case["vehicle_year"],
                    case["vin"],
                    case["symptom_description"],
                    case["issue_category"],
                    case["affected_system"],
                    case["urgency"],
                    case["ai_summary"],
                    case["technician_skill"],
                    json.dumps(case["required_parts"]),
                    case["warranty_active"],
                    case["warranty_status"],
                    case["requires_human_review"],
                    case["status"],
                    case["created_at"],
                    case["updated_at"]
                )
            )

            database_id = cursor.fetchone()[0]
            connection.commit()
            return database_id


@app.get("/health")
def health():
    return jsonify({"status": "ok"}), 200


@app.get("/ready")
def ready():
    try:
        with psycopg.connect(DATABASE_URL) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")

        return jsonify({
            "status": "ready",
            "database": "ok"
        }), 200

    except Exception:
        return jsonify({
            "status": "not_ready",
            "database": "unavailable"
        }), 503


@app.post("/service-cases")
def receive_service_case():
    provided_api_key = request.headers.get("X-API-Key")

    if not EXPECTED_API_KEY or provided_api_key != EXPECTED_API_KEY:
        return jsonify({
            "received": False,
            "error": "Unauthorized"
        }), 401

    case_data = request.get_json(silent=True) or {}

    case_id = str(
    case_data.get("case_id") or uuid.uuid4()
).strip()
    customer_name = case_data.get("customer_name", "").strip()
    customer_email = case_data.get("customer_email", "").strip().lower()
    vehicle_make = case_data.get("vehicle_make", "").strip()
    vehicle_model = case_data.get("vehicle_model", "").strip()
    symptom_description = case_data.get(
        "symptom_description",
        ""
    ).strip()

    vehicle_year = case_data.get("vehicle_year")
    vin = case_data.get("vin", "").strip()
    warranty_active = case_data.get("warranty_active")

    if not all([
        customer_name,
        customer_email,
        vehicle_make,
        vehicle_model,
        symptom_description
    ]):
        return jsonify({
            "received": False,
            "status": "invalid",
            "error": (
                "Customer name, email, vehicle make, vehicle model, "
                "and symptom description are required"
            )
        }), 400

    if case_already_exists(case_id):
        return jsonify({
            "received": False,
            "duplicate": True,
            "case_id": case_id,
            "message": "This service case was already processed"
        }), 200

    try:
        ai_result = classify_case(
            symptom_description,
            warranty_active
        )

    except Exception:
        return jsonify({
            "received": False,
            "status": "human_review",
            "case_id": case_id,
            "error": "AI classification failed"
        }), 422

    requires_human_review = (
        ai_result["urgency"] in ["High", "Critical"]
        or warranty_active is True
    )

    if warranty_active is True:
        warranty_status = "requires_review"
    elif warranty_active is False:
        warranty_status = "not_eligible"
    else:
        warranty_status = "unknown"

    status = (
        "awaiting_review"
        if requires_human_review
        else "classified"
    )

    timestamp = datetime.now(timezone.utc)

    case = {
        "case_id": case_id,
        "customer_name": customer_name,
        "customer_email": customer_email,
        "vehicle_make": vehicle_make,
        "vehicle_model": vehicle_model,
        "vehicle_year": vehicle_year,
        "vin": vin,
        "symptom_description": symptom_description,
        "issue_category": ai_result["issue_category"],
        "affected_system": ai_result["affected_system"],
        "urgency": ai_result["urgency"],
        "ai_summary": ai_result["summary"],
        "technician_skill": ai_result["technician_skill"],
        "required_parts": ai_result["required_parts"],
        "warranty_active": warranty_active,
        "warranty_status": warranty_status,
        "requires_human_review": requires_human_review,
        "status": status,
        "created_at": timestamp,
        "updated_at": timestamp
    }

    database_id = save_case(case)

    return jsonify({
        "received": True,
        "saved": True,
        "database_id": database_id,
        "case": case
    }), 200

@app.post("/service-cases/<case_id>/approval")
def approve_service_case(case_id):
    provided_api_key = request.headers.get("X-API-Key")

    if not EXPECTED_API_KEY or provided_api_key != EXPECTED_API_KEY:
        return jsonify({
            "received": False,
            "error": "Unauthorized"
        }), 401

    approval_data = request.get_json(silent=True) or {}
    decision = approval_data.get("decision", "").strip().lower()
    reviewer = approval_data.get("reviewer", "").strip()
    notes = approval_data.get("notes", "").strip()

    if decision not in ["approved", "rejected"] or not reviewer:
        return jsonify({
            "received": False,
            "status": "invalid",
            "error": "Decision and reviewer are required"
        }), 400

    with psycopg.connect(DATABASE_URL) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT requires_human_review
                FROM service_cases
                WHERE case_id = %s
                """,
                (case_id,)
            )

            row = cursor.fetchone()

            if row is None:
                return jsonify({
                    "received": False,
                    "error": "Service case not found"
                }), 404

            if not row[0]:
                return jsonify({
                    "received": False,
                    "error": "This case does not require human review"
                }), 409

            new_status = (
                "approved"
                if decision == "approved"
                else "rejected"
            )

            timestamp = datetime.now(timezone.utc)

            cursor.execute(
                """
                UPDATE service_cases
                SET warranty_status = %s,
                    requires_human_review = FALSE,
                    status = %s,
                    updated_at = %s
                WHERE case_id = %s
                """,
                (
                    decision,
                    new_status,
                    timestamp,
                    case_id
                )
            )

            cursor.execute(
                """
                INSERT INTO audit_events (
                    case_id,
                    event_type,
                    actor,
                    details
                )
                VALUES (%s, %s, %s, %s)
                """,
                (
                    case_id,
                    f"warranty_{decision}",
                    reviewer,
                    json.dumps({"notes": notes})
                )
            )

            connection.commit()

    return jsonify({
        "received": True,
        "case_id": case_id,
        "decision": decision,
        "status": new_status,
        "reviewer": reviewer
    }), 200
@app.get("/service-cases/<case_id>/resources")
def match_case_resources(case_id):
    provided_api_key = request.headers.get("X-API-Key")

    if not EXPECTED_API_KEY or provided_api_key != EXPECTED_API_KEY:
        return jsonify({
            "received": False,
            "error": "Unauthorized"
        }), 401

    with psycopg.connect(DATABASE_URL) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT technician_skill, required_parts
                FROM service_cases
                WHERE case_id = %s
                """,
                (case_id,)
            )

            case_row = cursor.fetchone()

            if case_row is None:
                return jsonify({
                    "received": False,
                    "error": "Service case not found"
                }), 404

            required_skill = case_row[0].lower()
            required_parts = case_row[1] or []

            cursor.execute(
                """
                SELECT id, name, skills, availability_status, location
                FROM technicians
                WHERE availability_status = 'available'
                """
            )

            technicians = cursor.fetchall()

            best_technician = None
            best_score = 0
            
            required_words = {
                word
                for word in re.findall(r"[a-z0-9]+", required_skill)
                if len(word) > 3
            }
            
            for technician in technicians:
                technician_words = {
                    word
                    for word in re.findall(r"[a-z0-9]+", technician[2].lower())
                    if len(word) > 3
                }
            
                score = len(required_words & technician_words)
            
                if score >= 2 and score > best_score:
                    best_score = score
                    best_technician = technician
            matched_parts = []
            all_parts_available = True
        
            for requested_part in required_parts:
                cursor.execute(
                    """
                    SELECT part_name, stock_quantity, warehouse_location
                    FROM parts_inventory
                    WHERE LOWER(part_name) LIKE LOWER(%s)
                    LIMIT 1
                    """,
                    (f"%{requested_part[:20]}%",)
                )
        
                part_row = cursor.fetchone()
        
                if part_row is None or part_row[1] <= 0:
                    all_parts_available = False
                    matched_parts.append({
                        "requested_part": requested_part,
                        "available": False
                    })
                else:
                    matched_parts.append({
                        "requested_part": requested_part,
                        "available": True,
                        "stock_quantity": part_row[1],
                        "warehouse_location": part_row[2]
                    })
        
            technician_result = None
        
            if best_technician:
                technician_result = {
                    "technician_id": best_technician[0],
                    "name": best_technician[1],
                    "skills": best_technician[2],
                    "location": best_technician[4]
                }
        
            resources_ready = (
                technician_result is not None
                and all_parts_available
            )
        
            cursor.execute(
                """
                UPDATE service_cases
                SET matched_technician_id = %s,
                    parts_available = %s,
                    updated_at = NOW()
                WHERE case_id = %s
                """,
                (
                    technician_result["technician_id"]
                    if technician_result else None,
                    all_parts_available,
                    case_id
                )
            )
        
            connection.commit()

    return jsonify({
        "received": True,
        "case_id": case_id,
        "technician": technician_result,
        "parts": matched_parts,
        "parts_available": all_parts_available,
        "resources_ready": resources_ready,
        "next_action": (
            "Propose appointment"
            if resources_ready
            else "Send to resource review"
        )
    }), 200
@app.post("/service-cases/<case_id>/appointment")
def propose_appointment(case_id):
    provided_api_key = request.headers.get("X-API-Key")

    if not EXPECTED_API_KEY or provided_api_key != EXPECTED_API_KEY:
        return jsonify({
            "received": False,
            "error": "Unauthorized"
        }), 401

    with psycopg.connect(DATABASE_URL) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT matched_technician_id, parts_available, urgency
                FROM service_cases
                WHERE case_id = %s
                """,
                (case_id,)
            )

            case_row = cursor.fetchone()

            if case_row is None:
                return jsonify({
                    "received": False,
                    "error": "Service case not found"
                }), 404

            technician_id, parts_available, urgency = case_row

            if not technician_id or not parts_available:
                return jsonify({
                    "received": False,
                    "status": "resource_review",
                    "error": "Technician or required parts are unavailable"
                }), 409

            cursor.execute(
                """
                SELECT id, name, location
                FROM technicians
                WHERE id = %s
                """,
                (technician_id,)
            )

            technician = cursor.fetchone()

            now = datetime.now(timezone.utc)

            sla_hours = {
                "Critical": 1,
                "High": 4,
                "Medium": 24,
                "Low": 72
            }.get(urgency, 24)

            proposed_start = now + timedelta(hours=2)
            proposed_end = proposed_start + timedelta(hours=1)
            sla_due_at = now + timedelta(hours=sla_hours)

            cursor.execute(
                """
                INSERT INTO appointments (
                    case_id,
                    technician_id,
                    proposed_start,
                    proposed_end,
                    sla_due_at,
                    status
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (case_id) DO NOTHING
                RETURNING id
                """,
                (
                    case_id,
                    technician_id,
                    proposed_start,
                    proposed_end,
                    sla_due_at,
                    "proposed"
                )
            )

            appointment_row = cursor.fetchone()

            if appointment_row is None:
                return jsonify({
                    "received": False,
                    "duplicate": True,
                    "case_id": case_id,
                    "message": "An appointment already exists"
                }), 200

            connection.commit()

    return jsonify({
        "received": True,
        "appointment_id": appointment_row[0],
        "case_id": case_id,
        "technician": {
            "id": technician[0],
            "name": technician[1],
            "location": technician[2]
        },
        "proposed_start": proposed_start,
        "proposed_end": proposed_end,
        "sla_due_at": sla_due_at,
        "status": "proposed"
    }), 200
if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5090,
        debug=True
    )
