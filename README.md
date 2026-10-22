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

The API enforces review status before downstream resource matching and appointment proposals; n8n is orchestration rather than the source of authorisation. This repository contains the API, database schema, tests, Docker configuration, CI and a sanitised inactive n8n JSON export. The export was clean-import verified with n8n 2.44.5; it still requires an uncommitted credential and controlled node testing before activation.

## Evidence and learning pack

- [Case study and architecture](docs/CASE_STUDY.md)
- [Three executable demonstration scenarios](docs/DEMO_SCENARIOS.md)
- [Owner learning and interview guide](docs/LEARNING_GUIDE.md)
- [Public demo boundaries](docs/PUBLIC_DEMO_BOUNDARIES.md)
- [Synthetic triage evaluation](evaluation/README.md)
- [Sanitised n8n workflow and setup](workflows/README.md)

The evidence pack documents verified behavior and limitations. It does not add customer metrics, claim a production deployment or turn the illustrative portfolio walkthrough into the backend.

## What is implemented

- Required intake fields, normalised customer email, API-key checks and case-ID duplicate detection.
- AI category, affected system, urgency, summary, technician skill and suggested parts, with required-field, urgency and list checks.
- `awaiting_review` for High/Critical classifications or active-warranty cases.
- Approval/rejection endpoint and PostgreSQL audit events containing reviewer and notes.
- Server-side state gates on resource matching and appointment proposals, plus row locking to serialize decisions and proposals for the same case.
- Keyword-based technician matching and text-based parts-inventory lookup.
- Resource availability rechecks before an appointment proposal, stored proposals and urgency-based SLA timestamps.
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
| GET | /service-cases/{case_id}/resources | Enforce review state, then look up resources and persist the match |
| POST | /service-cases/{case_id}/appointment | Enforce review state and recheck resources, then propose a slot |

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

### Review states and downstream actions

| Recorded state | Resource matching / appointment proposals |
| --- | --- |
| `awaiting_review` or pending review flag | HTTP 409; no downstream resource or appointment writes |
| `rejected` decision/status | HTTP 409 even when the pending-review flag is false |
| `classified`, no pending review, Low/Medium urgency and no active warranty | May proceed subject to resource checks |
| `approved`, no pending review | May proceed subject to resource checks |
| Unknown status/urgency, or High/Critical/active-warranty without approved status | HTTP 409; fail closed |

Only `awaiting_review` with its review flag set can transition to `approved` or `rejected`. A repeat or conflicting decision returns HTTP 409. Each decision updates the case and appends its audit event in one transaction. Case-row locks serialize concurrent decisions, resource matching and proposals. There is no reopening endpoint in this prototype.

Before a proposal, the matched technician must still be marked available and the required parts must still have stock. Shared row locks protect those checks through the proposal transaction, but **do not reserve inventory or a real calendar slot**. Proposal retries continue to use the existing one-appointment-per-case unique constraint.

## Tests and CI

The default suite contains **51 parametrized test cases**, including the original six intake tests and new review-state, authentication, unavailable-resource, decision/audit and duplicate-proposal regressions. Database and AI calls are mocked in that suite; it is not a real-model accuracy evaluation.

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt pytest
OPENAI_API_KEY=test-placeholder python -m pytest -q test_service_api.py test_evaluation.py
```

An additional **13 opt-in PostgreSQL integration cases** exercise real SQL with synthetic fixtures: pending/rejected blocks, approved and routine workflows, changed stock/technician availability, audit-failure rollback, concurrent conflicting decisions and duplicate concurrent proposals. AI classification is mocked; no paid API call or customer dataset is used. Each test creates and removes only its own random schema in a dedicated test database.

On a Mac with PostgreSQL 17 binaries and the `.venv` above:

```sh
bash scripts/run_database_tests.sh
# Override CONTROL_TOWER_PG_BIN if PostgreSQL binaries are elsewhere.
```

The runner creates a separate temporary cluster with TCP listening disabled, runs both suites and stops the cluster on exit. It retains test-only cluster/log files under the printed temporary path for inspection. It does not read `DATABASE_URL`, the Render database or the saved backup. Without the opt-in test connection, integration tests skip. GitHub Actions uses a separate PostgreSQL 17 service and an explicit test-only connection.

[GitHub Actions](https://github.com/Axhitgg/service-operations-control-tower/actions) is configured for the mocked suite, Docker build and SQL integration suite. Inspect actual runs after publication rather than treating local results as a hosted CI pass. No customer time-saving, revenue or production-adoption metrics have been measured.

## Important limitations

- This is a portfolio prototype, not a vehicle-diagnostic, emergency-response or warranty-adjudication system.
- State checks enforce the recorded approval decision, not the correctness of AI triage or an actual safety assessment. A dangerous message misclassified as Low/Medium can still follow the routine path.
- A shared API key is not role-based access control. The reviewer name is supplied by the caller, not verified against a user account.
- Technician matching uses word overlap; parts matching uses partial text. Neither validates real certification, geography, inventory reservations or calendar availability.
- AI calls use a bounded timeout and retry count configured by `MODEL_TIMEOUT_SECONDS` and `MODEL_MAX_RETRIES`.
- Every response includes `X-Request-ID`; a valid caller ID is preserved and an unsafe or missing value is replaced. Classification-failure logs record that ID and the exception type, not symptom text or customer details.
- Appointment starts are proposed within the urgency response window (Critical 30 minutes, High 2 hours, Medium 8 hours, Low 24 hours). This is a prototype scheduling rule, not a real calendar reservation.
- Appointment proposals use fixed urgency-based offsets within the recorded response window. They are not produced by a real scheduling optimiser and do not reserve a calendar slot.
- The unique case ID prevents duplicate rows during concurrent intake, but simultaneous retries can still repeat classification work. There is no durable retry queue or email-delivery ledger.
- Readiness verifies database connectivity, not the complete schema.
- Customer symptom text is sent to OpenAI. Do not submit real client details or credentials to the public demo. Keep secrets in environment variables and use unique keys instead of test fixtures.

## Author

[Akshit Singh](https://www.linkedin.com/in/akshit-singh-outlook/) - AI automation portfolio project.
