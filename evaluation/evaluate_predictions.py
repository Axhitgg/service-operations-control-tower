#!/usr/bin/env python3
"""Score saved synthetic predictions without calling an AI or live service."""

import argparse
import json
from collections import Counter
from pathlib import Path


URGENCIES = ("Low", "Medium", "High", "Critical")


def load_jsonl(path):
    rows = []
    with Path(path).open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise ValueError(f"{path}:{line_number}: invalid JSON") from error
    return rows


def index_unique(rows, source):
    indexed = {}
    for row in rows:
        case_id = row.get("case_id")
        if not case_id:
            raise ValueError(f"{source}: every row needs case_id")
        if case_id in indexed:
            raise ValueError(f"{source}: duplicate case_id {case_id}")
        indexed[case_id] = row
    return indexed


def score(expected_rows, prediction_rows):
    expected = index_unique(expected_rows, "dataset")
    predictions = index_unique(prediction_rows, "predictions")
    missing = sorted(set(expected) - set(predictions))
    extra = sorted(set(predictions) - set(expected))
    evaluated_ids = sorted(set(expected) & set(predictions))

    urgency_correct = 0
    review_correct = 0
    high_risk_total = 0
    high_risk_reviewed = 0
    confusion = Counter()

    for case_id in evaluated_ids:
        expected_row = expected[case_id]
        prediction = predictions[case_id]
        expected_urgency = expected_row["expected_urgency"]
        predicted_urgency = prediction.get("urgency")
        if expected_urgency not in URGENCIES:
            raise ValueError(f"dataset: invalid urgency for {case_id}")
        if predicted_urgency not in URGENCIES:
            raise ValueError(f"predictions: invalid urgency for {case_id}")

        expected_review = expected_row["expected_review"]
        predicted_review = prediction.get("requires_human_review")
        if not isinstance(expected_review, bool) or not isinstance(predicted_review, bool):
            raise ValueError(f"{case_id}: review values must be booleans")

        urgency_correct += predicted_urgency == expected_urgency
        review_correct += predicted_review == expected_review
        confusion[(expected_urgency, predicted_urgency)] += 1
        if expected_review:
            high_risk_total += 1
            high_risk_reviewed += predicted_review

    count = len(evaluated_ids)
    ratio = lambda value, total: round(value / total, 4) if total else None
    return {
        "dataset_cases": len(expected),
        "evaluated_cases": count,
        "missing_case_ids": missing,
        "extra_case_ids": extra,
        "urgency_exact_accuracy": ratio(urgency_correct, count),
        "review_decision_accuracy": ratio(review_correct, count),
        "required_review_recall": ratio(high_risk_reviewed, high_risk_total),
        "urgency_confusion": {
            expected_label: {
                predicted_label: confusion[(expected_label, predicted_label)]
                for predicted_label in URGENCIES
            }
            for expected_label in URGENCIES
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("predictions", help="JSONL containing case_id, urgency and requires_human_review")
    parser.add_argument(
        "--dataset",
        default=Path(__file__).with_name("synthetic_cases.jsonl"),
        help="labelled synthetic JSONL dataset",
    )
    args = parser.parse_args()
    result = score(load_jsonl(args.dataset), load_jsonl(args.predictions))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
