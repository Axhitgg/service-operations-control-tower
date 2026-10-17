# Service Operations Control Tower

An EV service-operations prototype that turns a customer symptom report into a classified case, a review decision, resource checks and an appointment proposal. Built with Python, Flask, OpenAI and PostgreSQL.

[Interactive portfolio walkthrough](https://akshit-portfolio-jlzx.onrender.com/#flagship) · [API health](https://service-operations-control-tower.onrender.com/health) · [API readiness](https://service-operations-control-tower.onrender.com/ready)

The walkthrough is an illustrative browser demo, separate from this backend. The API root `/` has no landing page. Hosted services may cold-start or be unavailable; the repository can also be run locally.

## Why build this?

A battery warning with loss of propulsion should not disappear among routine screen complaints. A service team also needs to know whether an appropriately skilled technician and the requested parts are available before suggesting an appointment. This project explores those handoffs without allowing an AI response to stand in for a technician diagnosis or a final decision on warranty coverage.

## Walk through three cases

| Customer report | Prototype behaviour | Operational purpose |
| --- | --- | --- |
| Screen freezes, warranty inactive | Classify; check technician and parts; allow an appointment proposal when resource checks pass | Give routine requests a structured next step |
| Battery warning and sudden power loss | A High/Critical classification or active warranty marks the case awaiting review | Make potentially risky cases visible for human review |
| Requested part out of stock | Resource result reports unavailable parts; appointment route returns resource-review error | Avoid proposing a slot without the recorded resources |

These are synthetic demonstration scenarios, not measured outcomes at a service company.

## Workflow and repository scope

```text
Customer / n8n intake -> Flask validation + duplicate-ID check -> OpenAI classification
                     -> PostgreSQL case record + review flags
                     -> Human decision and audit event, when required
                     -> Technician / inventory lookup -> Appointment proposal
```

The intended n8n orchestration must respect review status before calling downstream routes. This repository contains the API, database schema, tests, Docker configuration and CI; an importable n8n workflow is not included.

## What is implemented

- Required intake fields, normalised customer email, API-key checks and case-ID duplicate detection.
- AI category, affected system, urgency, summary, technician skill and suggested parts, with required-field, urgency and list checks.
- `awaiting_review` for High/Critical classifications or active-warranty cases.
- Approval/rejection endpoint and PostgreSQL audit events containing reviewer and notes.
- Keyword-based technician matching and text-based parts-inventory lookup.
- Resource availability checks, stored appointment proposals and urgency-based SLA timestamps.
- Health/readiness endpoints and Gunicorn access/error logging to standard output.

## Run with Docker Compose

Requirements: Docker with Compose and an OpenAI API key. Real classification requests can incur API charges.

1. Clone this repository and enter the folder.
2. Create a local, untracked `.env` file with your own values:

```dotenv
OPENAI_API_KEY=replace-with-your-own-key
SERVICE_API_KEY=replace-with-a-unique-local-secret
POSTGRES_PASSWORD=replace-with-a-url-safe-local-password
```

3. Start the API and PostgreSQL:

```sh
docker compose up --build -d
curl http://127.0.0.1:5090/health
curl http://127.0.0.1:5090/ready
```

Compose supplies DATABASE_URL and runs `init.sql` when creating a new database volume, including synthetic technicians and parts inventory. Existing volumes do not automatically receive schema changes. Use a reviewed migration for existing data; do not delete a database volume just to refresh the schema.

Stop without deleting stored data:

```sh
docker compose down
```

## API reference

All case endpoints require `X-API-Key` matching SERVICE_API_KEY. Health/readiness do not require the key.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | /health | Check that the API process responds |
| GET | /ready | Check database connectivity with SELECT 1 |
| POST | /service-cases | Validate, classify and store a case |
| POST | /service-cases/{case_id}/approval | Record approved/rejected decision, reviewer and notes |
| GET | /service-cases/{case_id}/resources | Look up resources and persist the match result |
| POST | /service-cases/{case_id}/appointment | Propose a slot when recorded technician/parts checks pass |

Example intake body. Use fictional details only:

```json
{
  "case_id": "demo-case-001",
  "customer_name": "Demo Customer",
  "customer_email": "demo@example.com",
  "vehicle_make": "Hyundai",
  "vehicle_model": "Kona Electric",
  "vehicle_year": 2023,
  "vin": "DEMO-NOT-A-REAL-VIN",
  "symptom_description": "The infotainment screen freezes occasionally, but the vehicle drives normally.",
  "warranty_active": false
}
```

Approval body for a case awaiting review:

```json
{
  "decision": "approved",
  "reviewer": "demo-reviewer",
  "notes": "Reviewed this synthetic demonstration case."
}
```

Known duplicate case IDs return HTTP 200 with `duplicate: true` and `received: false`. Reuse a stable case_id for retries; omitting it generates a new ID. Classification failure returns HTTP 422 and a human-review status, but does not save a new case. The calling workflow must handle that failure.

## Tests and CI

The repository contains six Pytest tests: missing API key, missing required field, duplicate case ID, successful low-risk save, high-risk review flag and classification failure. AI/database operations are mocked for those paths; these are not end-to-end database, approval or scheduling tests.

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt pytest
OPENAI_API_KEY=test-placeholder python -m pytest -q test_service_api.py
```

[GitHub Actions](https://github.com/Axhitgg/service-operations-control-tower/actions) runs the suite and builds the Docker image. Inspect the current run rather than assuming a historical result applies forever. No customer time-saving, revenue or production-adoption metrics have been measured.

## Important limitations

- This is a portfolio prototype, not a vehicle-diagnostic, emergency-response or warranty-adjudication system.
- Review flags are not a complete server-enforced approval gate: resource and appointment routes do not independently reject unapproved/rejected cases. The intended caller must respect state. Add server-side state checks before real use.
- A shared API key is not role-based access control. The reviewer name is supplied by the caller, not verified against a user account.
- Technician matching uses word overlap; parts matching uses partial text. Neither validates real certification, geography, inventory reservations or calendar availability.
- Appointment proposals use a fixed future offset. SLA deadlines are recorded, not enforced by a scheduling optimiser; some proposed times can fall after the recorded deadline.
- Duplicate checks are not full concurrent idempotency, and there is no durable retry queue or email-delivery ledger.
- Readiness verifies database connectivity, not the complete schema.
- Customer symptom text is sent to OpenAI. Do not submit real client details or credentials to the public demo. Keep secrets in environment variables and use unique keys instead of test fixtures.

## Author

[Akshit Singh](https://www.linkedin.com/in/akshit-singh-outlook/) - AI automation portfolio project.
