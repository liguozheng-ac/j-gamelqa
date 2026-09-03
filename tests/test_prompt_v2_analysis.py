import unittest

import pandas as pd

from j_gamelqa.evaluate import evaluate_detections
from j_gamelqa.hybrid import merge_hybrid_predictions
from j_gamelqa.models import Issue
from j_gamelqa.prompt_v2_analysis import (
    analysis_artifact_paths,
    build_prompt_comparison,
    paired_prompt_changes,
)


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


def issue(string_id, issue_type, checker="japanese_llm"):
    return Issue(
        string_id=string_id,
        checker=checker,
        issue_type=issue_type,
        severity="major",
        message="test",
    )


def references():
    return pd.DataFrame(
        [
            ("A1", "S1", "translationese", "minor", "", "", "{}", "test"),
            ("A2", "S2", "keigo_mismatch", "major", "", "", "{}", "test"),
        ],
        columns=REFERENCE_COLUMNS,
    )


class PromptV2AnalysisTests(unittest.TestCase):
    def test_paired_changes_and_type_change_are_detected(self):
        v1 = [issue("S1", "mistranslation"), issue("S2", "keigo_mismatch")]
        v2 = [issue("S1", "translationese"), issue("S3", "addition")]
        changes = paired_prompt_changes(references(), v1, v2)
        self.assertEqual(
            [(x["string_id"], x["issue_type"]) for x in changes["resolved_false_positives"]],
            [("S1", "mistranslation")],
        )
        self.assertEqual(
            [(x["string_id"], x["issue_type"]) for x in changes["new_false_positives"]],
            [("S3", "addition")],
        )
        self.assertEqual(changes["type_changes"][0]["removed_types"], ["mistranslation"])
        self.assertEqual(changes["type_changes"][0]["added_types"], ["translationese"])

    def test_prompt_comparison_delta_uses_shared_evaluator(self):
        v1 = [issue("S1", "mistranslation"), issue("S2", "keigo_mismatch")]
        v2 = [issue("S1", "translationese")]
        v1_eval = evaluate_detections(references(), v1)
        v2_eval = evaluate_detections(references(), v2)
        v1_eval["experiment_id"] = "v1"
        v2_eval["experiment_id"] = "v2"
        comparison = build_prompt_comparison(
            references(), v1, v2, v1_eval, v2_eval
        )
        self.assertEqual(comparison["overall"]["prompt_v2"]["tp"], 1)
        self.assertEqual(comparison["overall"]["delta"]["fp"], -1)
        self.assertEqual(comparison["overall"]["delta"]["fn"], 0)

    def test_hybrid_prompt_v2_keeps_rules_and_filters_llm_rule_types(self):
        rules = [issue("S4", "number_missing", "number")]
        llm = [
            issue("S1", "translationese"),
            issue("S5", "number_mismatch"),
        ]
        merged = merge_hybrid_predictions(rules, llm)
        self.assertEqual(
            [(x.string_id, x.issue_type) for x in merged.predictions],
            [("S4", "number_missing"), ("S1", "translationese")],
        )
        self.assertEqual(
            merged.llm_predictions_excluded_from_hybrid[0].issue_type,
            "number_mismatch",
        )

    def test_analysis_artifacts_are_separate_from_v1(self):
        paths = set(analysis_artifact_paths("outputs").values())
        self.assertNotIn(
            analysis_artifact_paths("outputs")["prompt_comparison"].parent
            / "qwen35_9b_with_context_evaluation.json",
            paths,
        )


if __name__ == "__main__":
    unittest.main()
