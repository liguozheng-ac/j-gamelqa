import unittest

import pandas as pd

from j_gamelqa.evaluate import evaluate_detections
from j_gamelqa.hybrid import merge_hybrid_predictions
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


def prediction(string_id, issue_type, checker):
    return Issue(
        string_id=string_id,
        checker=checker,
        issue_type=issue_type,
        severity="major",
        message="test",
        needs_human_review=checker == "japanese_llm",
    )


class HybridMergeTests(unittest.TestCase):
    def test_all_rule_predictions_are_retained(self):
        rules = [
            prediction("S1", "number_mismatch", "number"),
            prediction("S2", "placeholder_missing", "placeholder"),
        ]
        result = merge_hybrid_predictions(rules, [])
        self.assertEqual(result.predictions, rules)

    def test_llm_required_prediction_is_added(self):
        llm_issue = prediction("S1", "keigo_mismatch", "japanese_llm")
        result = merge_hybrid_predictions([], [llm_issue])
        self.assertEqual(result.predictions, [llm_issue])

    def test_rule_addressable_llm_prediction_is_excluded_and_diagnosed(self):
        llm_rule_issue = prediction("S1", "number_mismatch", "japanese_llm")
        result = merge_hybrid_predictions([], [llm_rule_issue])
        self.assertEqual(result.predictions, [])
        self.assertEqual(
            result.llm_predictions_excluded_from_hybrid, [llm_rule_issue]
        )

    def test_unknown_llm_prediction_is_excluded_and_diagnosed(self):
        unknown = prediction("S1", "unregistered_issue", "japanese_llm")
        result = merge_hybrid_predictions([], [unknown])
        self.assertEqual(result.predictions, [])
        self.assertEqual(
            result.llm_predictions_excluded_from_hybrid,
            [unknown],
        )

    def test_llm_only_predictions_are_not_mutated_by_hybrid(self):
        llm_predictions = [
            prediction("S1", "number_mismatch", "japanese_llm"),
            prediction("S1", "keigo_mismatch", "japanese_llm"),
        ]
        original_ids = [id(item) for item in llm_predictions]
        result = merge_hybrid_predictions([], llm_predictions)
        self.assertEqual(len(llm_predictions), 2)
        self.assertEqual([id(item) for item in llm_predictions], original_ids)
        self.assertEqual(
            [item.issue_type for item in result.predictions],
            ["keigo_mismatch"],
        )

    def test_merge_duplicate_keys_are_preserved_and_reported(self):
        rule_issue = prediction("S1", "keigo_mismatch", "rule_test")
        llm_issue = prediction("S1", "keigo_mismatch", "japanese_llm")
        result = merge_hybrid_predictions([rule_issue], [llm_issue])
        self.assertEqual(len(result.predictions), 2)
        self.assertEqual(
            result.duplicate_predictions,
            [{"string_id": "S1", "issue_type": "keigo_mismatch", "count": 2}],
        )

    def test_evaluation_deduplicates_merged_detection_keys(self):
        rule_issue = prediction("S1", "keigo_mismatch", "rule_test")
        llm_issue = prediction("S1", "keigo_mismatch", "japanese_llm")
        merged = merge_hybrid_predictions([rule_issue], [llm_issue])
        references = pd.DataFrame(
            [
                (
                    "A1",
                    "S1",
                    "keigo_mismatch",
                    "major",
                    "",
                    "",
                    "{}",
                    "test",
                )
            ],
            columns=REFERENCE_COLUMNS,
        )
        evaluation = evaluate_detections(references, merged.predictions)
        self.assertEqual(evaluation["overall_micro"]["tp"], 1)
        self.assertEqual(evaluation["unique_prediction_detection_count"], 1)
        self.assertEqual(evaluation["raw_prediction_count"], 2)
