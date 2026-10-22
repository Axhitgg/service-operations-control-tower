import json
from pathlib import Path

import pytest

from evaluation.evaluate_predictions import load_jsonl, score


DATASET = Path(__file__).parent / "evaluation" / "synthetic_cases.jsonl"


def test_synthetic_dataset_is_balanced_and_unique():
    rows = load_jsonl(DATASET)
    assert len(rows) == 16
    assert len({row["case_id"] for row in rows}) == 16
    assert {
        urgency: sum(row["expected_urgency"] == urgency for row in rows)
        for urgency in ("Low", "Medium", "High", "Critical")
    } == {"Low": 4, "Medium": 4, "High": 4, "Critical": 4}


def test_evaluator_reports_safety_recall_and_missing_ids():
    expected = [
        {"case_id": "a", "expected_urgency": "Critical", "expected_review": True},
        {"case_id": "b", "expected_urgency": "Low", "expected_review": False},
        {"case_id": "c", "expected_urgency": "Medium", "expected_review": True},
    ]
    predictions = [
        {"case_id": "a", "urgency": "High", "requires_human_review": False},
        {"case_id": "b", "urgency": "Low", "requires_human_review": False},
    ]

    result = score(expected, predictions)
    assert result["urgency_exact_accuracy"] == 0.5
    assert result["review_decision_accuracy"] == 0.5
    assert result["required_review_recall"] == 0.0
    assert result["missing_case_ids"] == ["c"]


def test_evaluator_rejects_duplicate_predictions():
    expected = [{"case_id": "a", "expected_urgency": "Low", "expected_review": False}]
    predictions = [
        {"case_id": "a", "urgency": "Low", "requires_human_review": False},
        {"case_id": "a", "urgency": "Low", "requires_human_review": False},
    ]

    with pytest.raises(ValueError, match="duplicate case_id"):
        score(expected, predictions)
