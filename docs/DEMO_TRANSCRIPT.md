# Two-minute demo transcript

This is a caption-ready script for a short screen recording. Use only fictional case IDs and data. Keep API keys, environment variables, database credentials and personal details outside the recording.

## 0:00–0:15 — problem and architecture

**On screen:** repository README, then the workflow diagram.

**Narration / captions:**

> This Service Operations Control Tower turns an EV service request into a structured case, a review decision, resource checks and an appointment proposal. Flask owns the business rules, PostgreSQL stores the state and audit trail, OpenAI structures the initial report, and n8n can orchestrate the steps.

## 0:15–0:40 — routine request

**On screen:** Scenario 1 in `docs/DEMO_SCENARIOS.md`, followed by a fictional Low or Medium case response. Hide the API key.

**Narration / captions:**

> A routine request with inactive warranty can move from classification to resource checks. If the recorded technician and parts are available, the API can create one proposed appointment. Repeating the proposal returns the existing result rather than creating a second appointment.

## 0:40–1:15 — human-review gate

**On screen:** a fictional High/Critical or active-warranty response with `awaiting_review`, then the HTTP 409 response from a downstream route.

**Narration / captions:**

> A risky classification or active warranty changes the route. The case is marked awaiting review, and the API itself blocks resource matching and appointment creation with HTTP 409. This is important because the visual workflow is not the security boundary. After an explicit approval is recorded, the downstream route becomes available and the audit event keeps the reviewer decision.

## 1:15–1:40 — fail-closed behavior

**On screen:** the rejected-case or changed-resource test from Scenario 3 and the passing assertion that no appointment row was added.

**Narration / captions:**

> Rejection remains blocked even after the pending flag is cleared. The service also rechecks technician and parts availability before proposing a slot, so a stale earlier match cannot silently pass. Concurrent requests with the same case ID create one stored case.

## 1:40–2:00 — evidence and boundaries

**On screen:** GitHub Actions with both checks passing, the Render deployment marked Live, `/health`, `/ready`, and `docs/PUBLIC_DEMO_BOUNDARIES.md`.

**Narration / captions:**

> The automated suite covers the approval gates, concurrency, audit rollback, request tracing and SLA timing with synthetic data. The live service reports healthy and database ready. This is still a prototype: it does not diagnose vehicles, decide real warranty claims, reserve inventory or book a real calendar. The value here is the controlled workflow, test evidence and explicit failure boundaries—not invented customer metrics.

## Recording checklist

- Use a fresh fictional case ID and synthetic contact data.
- Crop or blur every secret, token, connection string and account menu.
- Keep the video close to two minutes; use the narration above as captions.
- Show one blocked path and one permitted path, not only the happy path.
- End with the limitations slide; do not claim users, savings, accuracy or production bookings.
- Retain the final video URL and recording date when one is published. This transcript alone does not prove that a video was recorded.
