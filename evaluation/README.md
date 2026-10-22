# Synthetic triage evaluation

This folder provides a small, labelled, fictional dataset and an offline scoring tool. It is designed to expose unsafe under-triage and review-routing mistakes without sending any customer information or making a paid model call.

The 16 cases are balanced across Low, Medium, High and Critical urgency. Labels are human-authored expectations for this prototype, not clinical, engineering or vehicle-manufacturer guidance. Active-warranty cases are expected to require review even when urgency is Low or Medium because that is the application's current policy.

## Prediction format

Save one JSON object per line:

```json
{"case_id":"eval-001","urgency":"Low","requires_human_review":false}
```

Then run:

```bash
python evaluation/evaluate_predictions.py path/to/predictions.jsonl
```

The report includes exact urgency accuracy, review-decision accuracy, recall for cases that must be reviewed, missing/extra IDs and an urgency confusion matrix. For a safety-oriented prototype, inspect every false negative rather than relying on one aggregate score.

## Honest evidence boundary

- Do not call the labels ground truth, customer outcomes or production accuracy.
- Do not publish a score until the prediction file, model/version, prompt, date and run conditions are retained.
- A model score does not prove the workflow is safe. The human-review and fail-closed controls remain necessary.
- The evaluator makes no network request. Generating fresh model predictions is deliberately outside this script so it cannot silently spend money or send data.
