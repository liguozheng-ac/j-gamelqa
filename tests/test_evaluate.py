import unittest

import pandas as pd

from j_gamelqa.evaluate import evaluate_detections
from j_gamelqa.models import Issue


REFERENCE_COLUMNS = (
    "annotation_id",
    "string_id",
    "issue_type",
    "severity",
    "source_span",
    "target_span",
    "evidence",
    "annotation_note",
)


def references(*rows):
    return pd.DataFrame(rows, columns=REFERENCE_COLUMNS)


def reference(annotation_id, string_id, issue_type, severity="major"):
    return (
        annotation_id,
        string_id,
        issue_type,
        severity,
        "reference source span",
        "reference target span",
        "{}",
        "test reference",
    )


def prediction(string_id, issue_type, severity="major", source_span="prediction span"):
    return Issue(
        string_id=string_id,
        checker="test",
        issue_type=issue_type,
        severity=severity,
        message="test prediction",
        source_span=source_span,
    )


class DetectionEvaluationTests(unittest.TestCase):
    def test_perfect_prediction(self):
        result = evaluate_detections(
            references(reference("A1", "S1", "placeholder_missing")),
            [prediction("S1", "placeholder_missing")],
        )
        self.assertEqual(result["overall_micro"]["tp"], 1)
        self.assertEqual(result["overall_micro"]["f1"], 1.0)

    def test_false_positive(self):
        result = evaluate_detections(references(), [prediction("S1", "number_extra")])
        self.assertEqual(result["overall_micro"]["fp"], 1)
        self.assertEqual(len(result["false_positives"]), 1)

    def test_false_negative(self):
        result = evaluate_detections(
            references(reference("A1", "S1", "omission")), []
        )
        self.assertEqual(result["overall_micro"]["fn"], 1)
        self.assertEqual(len(result["false_negatives"]), 1)

    def test_tp_fp_and_fn_together(self):
        result = evaluate_detections(
            references(
                reference("A1", "S1", "placeholder_missing"),
                reference("A2", "S2", "omission"),
            ),
            [
                prediction("S1", "placeholder_missing"),
                prediction("S3", "number_extra"),
            ],
        )
        self.assertEqual(
            {key: result["overall_micro"][key] for key in ("tp", "fp", "fn")},
            {"tp": 1, "fp": 1, "fn": 1},
        )

    def test_zero_predictions_is_safe(self):
        result = evaluate_detections(
            references(reference("A1", "S1", "mistranslation")), []
        )
        self.assertEqual(result["overall_micro"]["precision"], 0.0)
        self.assertEqual(result["overall_micro"]["recall"], 0.0)
        self.assertEqual(result["overall_micro"]["f1"], 0.0)

    def test_zero_references_is_safe(self):
        result = evaluate_detections(references(), [])
        self.assertEqual(result["overall_micro"]["precision"], 0.0)
        self.assertEqual(result["overall_micro"]["recall"], 0.0)
        self.assertEqual(result["overall_micro"]["f1"], 0.0)

    def test_overall_micro_values_are_computed(self):
        result = evaluate_detections(
            references(
                reference("A1", "S1", "placeholder_missing"),
                reference("A2", "S2", "omission"),
            ),
            [
                prediction("S1", "placeholder_missing"),
                prediction("S3", "number_extra"),
            ],
        )
        metrics = result["overall_micro"]
        self.assertAlmostEqual(metrics["precision"], 0.5)
        self.assertAlmostEqual(metrics["recall"], 0.5)
        self.assertAlmostEqual(metrics["f1"], 0.5)

    def test_per_issue_type_metrics(self):
        result = evaluate_detections(
            references(reference("A1", "S1", "placeholder_missing")),
            [
                prediction("S1", "placeholder_missing"),
                prediction("S2", "number_extra"),
            ],
        )
        per_type = {row["issue_type"]: row for row in result["per_issue_type"]}
        self.assertEqual(per_type["placeholder_missing"]["tp"], 1)
        self.assertEqual(per_type["placeholder_missing"]["reference_count"], 1)
        self.assertEqual(per_type["placeholder_missing"]["prediction_count"], 1)
        self.assertEqual(per_type["number_extra"]["fp"], 1)
        self.assertEqual(per_type["number_extra"]["reference_count"], 0)
        self.assertEqual(per_type["number_extra"]["prediction_count"], 1)

    def test_rule_addressable_filter_excludes_llm_required_issue(self):
        result = evaluate_detections(
            references(
                reference("A1", "S1", "placeholder_missing"),
                reference("A2", "S2", "omission"),
            ),
            [prediction("S1", "placeholder_missing")],
        )
        self.assertEqual(result["overall_micro"]["fn"], 1)
        self.assertEqual(
            result["rule_addressable_micro"],
            {"tp": 1, "fp": 0, "fn": 0, "precision": 1.0, "recall": 1.0, "f1": 1.0},
        )

    def test_llm_required_micro_uses_only_llm_required_types(self):
        result = evaluate_detections(
            references(
                reference("A1", "S1", "keigo_mismatch"),
                reference("A2", "S2", "mistranslation"),
                reference("A3", "S3", "number_missing"),
            ),
            [
                prediction("S1", "keigo_mismatch"),
                prediction("S4", "translationese"),
                prediction("S3", "number_missing"),
            ],
        )
        self.assertEqual(
            result["llm_required_micro"],
            {
                "tp": 1,
                "fp": 1,
                "fn": 1,
                "precision": 0.5,
                "recall": 0.5,
                "f1": 0.5,
            },
        )

    def test_duplicate_prediction_counts_once_and_is_reported(self):
        result = evaluate_detections(
            references(reference("A1", "S1", "placeholder_missing")),
            [
                prediction("S1", "placeholder_missing"),
                prediction("S1", "placeholder_missing"),
            ],
        )
        self.assertEqual(result["overall_micro"]["tp"], 1)
        self.assertEqual(result["raw_prediction_count"], 2)
        self.assertEqual(result["unique_prediction_detection_count"], 1)
        self.assertEqual(
            result["duplicate_predictions"],
            [{"string_id": "S1", "issue_type": "placeholder_missing", "count": 2}],
        )

    def test_unknown_prediction_is_overall_fp_and_reported(self):
        result = evaluate_detections(
            references(), [prediction("S1", "some_new_error_type")]
        )
        self.assertEqual(result["overall_micro"]["fp"], 1)
        self.assertEqual(result["unknown_prediction_types"], ["some_new_error_type"])
        self.assertEqual(
            result["unknown_prediction_occurrences"],
            [{"string_id": "S1", "issue_type": "some_new_error_type", "count": 1}],
        )

    def test_severity_difference_does_not_change_detection_tp(self):
        result = evaluate_detections(
            references(reference("A1", "S1", "placeholder_missing", "major")),
            [prediction("S1", "placeholder_missing", "minor")],
        )
        self.assertEqual(result["overall_micro"]["tp"], 1)

    def test_span_difference_does_not_change_detection_tp(self):
        result = evaluate_detections(
            references(reference("A1", "S1", "keigo_mismatch")),
            [prediction("S1", "keigo_mismatch", source_span="different span")],
        )
        self.assertEqual(result["overall_micro"]["tp"], 1)
