# Demonstration scenarios

Use fictional details and a local/test deployment. Do not paste a real API key into screenshots, recordings or committed files. Replace `$BASE_URL` and `$SERVICE_API_KEY` in your own shell environment.

## Scenario 1 — routine request

Purpose: show a Low/Medium, inactive-warranty case proceeding without a review decision.

1. `POST /service-cases` with a unique `case_id`, `warranty_active: false` and a routine fictional symptom.
2. Verify the saved case has `status: classified` and `requires_human_review: false`.
3. `GET /service-cases/{case_id}/resources`.
4. If `resources_ready` is true, `POST /service-cases/{case_id}/appointment`.
5. Verify a proposal is returned. Repeat the proposal request and verify the duplicate response rather than a second appointment.

Expected transition:

```text
new -> classified -> resources checked -> proposed
```

Important: live model output is nondeterministic. The controlled tests mock the classification so the expected urgency is fixed.

## Scenario 2 — risky request requires approval

Purpose: demonstrate that UI or workflow branching is not the only protection; the API itself blocks downstream action.

1. Submit a fictional battery/power-loss case with `warranty_active: true`.
2. Verify `status: awaiting_review` and `requires_human_review: true`.
3. Call both downstream routes before a decision.
4. Verify both return HTTP 409 with `status: awaiting_review` and create no appointment.
5. `POST /service-cases/{case_id}/approval` with an approved decision and fictional reviewer.
6. Match resources and then propose an appointment.

Expected transition:

```text
new -> awaiting_review -> approved -> resources checked -> proposed
```

## Scenario 3 — rejection and changed resources fail closed

Purpose: show that clearing a pending flag is not equivalent to authorisation and that stale resource checks are revalidated.

Rejection path:

1. Create a risky synthetic case.
2. Record a rejected decision.
3. Call resource matching and appointment routes.
4. Verify HTTP 409 with `status: rejected` even though the pending-review flag has been cleared.

Changed-resource path (isolated test database only):

1. Approve a risky synthetic case and obtain `resources_ready: true`.
2. Mark the selected technician busy or set required stock to zero.
3. Request an appointment.
4. Verify HTTP 409 `resource_review` and zero new appointment rows.

Expected transitions:

```text
awaiting_review -> rejected -> blocked
approved -> resources checked -> resource changed -> blocked
```

## Evidence to capture for a short demo

- The request type and fictional case ID, with secrets hidden.
- The HTTP status and relevant state fields.
- The database row count or test assertion that no forbidden appointment was created.
- The approved route succeeding only after the review decision and resource recheck.
- A final slide naming the prototype limitations; do not claim customer impact.

