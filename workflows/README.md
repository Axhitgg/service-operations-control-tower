# n8n workflow export

`service-operations-control-tower.json` is a sanitised, inactive workflow export containing three webhook branches:

- intake → create service case → return API result;
- review decision → record approved/rejected decision → return API result;
- continue → match current resources → request appointment proposal → return API result.

The backend remains the source of truth. n8n does not override review state: pending, rejected or unavailable-resource cases are blocked by the Flask API. The continuation branch deliberately lets the API make both decisions rather than treating a canvas branch as authorisation.

## Import and configure

1. Import `service-operations-control-tower.json` from the n8n workflow menu.
2. Keep the workflow inactive while configuring it.
3. In each HTTP Request node, replace `https://YOUR-RENDER-SERVICE.onrender.com` with the intended API base URL.
4. Replace `REPLACE_AFTER_IMPORT` by configuring n8n Header Auth credentials for `X-API-Key`. Do not save a real key directly in a workflow that will be exported or committed.
5. Verify every HTTP node uses the intended Header Auth credential, then remove the placeholder header values.
6. Use the Webhook node test URLs with fictional payloads. Production URLs become available only after publishing the workflow.
7. Test pending, approved, rejected and resource-unavailable cases before publishing.

The export contains no credential object, real API key, execution history, pinned customer data or production case. n8n's documentation warns that workflow exports can include credential names/IDs and manually imported authentication headers; inspect any future re-export before sharing it.

## Expected payloads

### Intake

POST fictional JSON to the intake webhook. The body is forwarded to `POST /service-cases`.

### Decision

POST to `/control-tower-decision/{case_id}` with:

```json
{
  "decision": "approved",
  "reviewer": "synthetic-reviewer",
  "notes": "Controlled demonstration only"
}
```

### Continue

POST to `/control-tower-continue/{case_id}` with an empty JSON object. The workflow requests current resources and then an appointment proposal. If review is pending/rejected or resources are unavailable, the API's blocked result is returned and no appointment is created.

## Verification boundary

The JSON is syntax-checked in this repository. Import and node execution in a clean n8n instance remain required before claiming the workflow is fully import-verified. Do not publish or activate it until that check is complete.

