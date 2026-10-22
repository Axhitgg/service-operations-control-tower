# Owner learning guide

The goal is not to memorise the code. The goal is to explain why each layer exists, predict a failure and make one small change independently.

## 1. Trace one request

Read these functions in order:

1. `receive_service_case` — authentication, validation, duplicate check, classification and persistence.
2. `classify_case` — external model call and output validation.
3. `approve_service_case` — legal state transition, case lock, update and audit event.
4. `case_action_blocker` — shared authorisation rule for downstream actions.
5. `match_case_resources` — case lock, gate, technician/parts lookup and recorded result.
6. `propose_appointment` — gate, resource recheck, shared locks and unique appointment insert.

After each function, answer without looking:

- What data enters?
- What data is trusted, validated or merely recorded?
- What database change occurs?
- What can fail?
- What prevents a repeated or concurrent action?

## 2. Core interview explanations

### Why does rejection still need an explicit status check?

The review flag represents whether a decision is pending. A false flag means a decision exists; it does not say the decision was approval. Authorisation therefore uses both the pending flag and the recorded status.

### Why return HTTP 409?

The request can be syntactically valid and authenticated while conflicting with the case's current state. `409 Conflict` communicates that the caller must resolve the workflow state rather than retry blindly.

### Why use `FOR UPDATE` for a decision?

Two reviewers could otherwise read the same pending state and both write decisions. The row lock serializes that read-modify-write sequence so only one transition succeeds.

### Why write the decision and audit event in one transaction?

If the case changes but the audit insert fails, the system would have an unaudited decision. A single transaction rolls both operations back together.

### Why is a unique appointment constraint still useful with a row lock?

The row lock serializes the normal application path. The database uniqueness constraint remains a final invariant against duplicate rows, including mistakes in another caller or future code path.

### What does the AI not decide?

The model proposes structured classification fields. It does not authenticate a reviewer, diagnose a vehicle, determine legal warranty coverage, reserve stock or book a real calendar slot.

## 3. Short practical exercises

Complete these in order. Run the relevant tests after each change.

1. Add a new test asserting that a malformed approval decision returns HTTP 400 before touching the database.
2. Intentionally change the rejected-case rule to allow rejection, run the tests and identify which regression fails. Restore the rule.
3. Add a test for an unknown case ID on one downstream route without copying an existing test verbatim.
4. Explain why `classification failure` currently returns review status without saving a case, then propose one safe persistence design before changing code.
5. Owner-led change: add a small non-sensitive field to a health/readiness response or improve one validation message, update its test and open a documentation-sized pull request.

Do not begin the next major feature until you can explain the current state machine and one concurrency test in your own words.

## 4. Honest 60-second project explanation

“I built an EV service-operations prototype that turns an unstructured service request into a structured case, records human decisions for risky or warranty-active cases, checks technician and parts availability and proposes an appointment. I found that downstream routes could rely on a cleared review flag without distinguishing approval from rejection, so I added server-side state guards, row locks, atomic audit writes and resource rechecks. The project has mocked regression tests and isolated PostgreSQL concurrency tests. It remains a portfolio prototype: AI classification can be wrong, reviewer identity uses a shared key and resource checks do not reserve real inventory or calendars.”

