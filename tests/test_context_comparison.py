import unittest

import pandas as pd

from j_gamelqa.context_comparison import (
    CONTEXT_SENSITIVE_ISSUES,
    calculate_metric_delta,
    compare_context_experiments,
    paired_detection_changes,
)
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


def references():
    return pd.DataFrame(
        [
            ("A1", "S1", "keigo_mismatch", "major", "", "", "{}", "test"),
            (
                "A2",
                "S2",
                "first_person_mismatch",
                "major",
                "",
                "",
                "{}",
                "test",
            ),
        ],
        columns=REFERENCE_COLUMNS,
    )


def prediction(string_id, issue_type):
    return Issue(
        string_id=string_id,
        checker="japanese_llm",
        issue_type=issue_type,
        severity="major",
        message="test",
        needs_human_review=True,
    )


def config(mode):
    return {
        "experiment_id": f"test_{mode}",
        "input_mode": mode,
        "model": "qwen3.5:9b",
        "provider": "ollama",
        "provider_endpoint": "http://127.0.0.1:11434/api/generate",
        "temperature": 0,
        "thinking": False,
        "stream": False,
        "prompt_version": "v1",
        "parser_policy": "stage_6a_strict_no_repair",
        "retry_policy": "off",
        "structured_output": False,
        "timeout_seconds": 120,
        "dataset": "same",
        "dataset_item_count": 48,
        "dev_path": "dev.csv",
        "glossary_path": "glossary.csv",
        "annotations_path_for_evaluation_only": "annotations.csv",
    }


class ContextComparisonTests(unittest.TestCase):
    def setUp(self):
        self.references = references()
        self.no_context = [
            prediction("S2", "first_person_mismatch"),
            prediction("S3", "mistranslation"),
        ]
        self.with_context = [
            prediction("S1", "keigo_mismatch"),
            prediction("S4", "character_voice_mismatch"),
        ]
        self.no_evaluation = evaluate_detections(
            self.references, self.no_context
        )
        self.with_evaluation = evaluate_detections(
            self.references, self.with_context
        )
        self.no_evaluation["protocol_metrics"] = {"provider_failures": 0}
        self.with_evaluation["protocol_metrics"] = {"provider_failures": 0}

    def test_delta_is_with_context_minus_no_context(self):
        delta = calculate_metric_delta(
            {"tp": 1, "fp": 3, "fn": 2, "precision": 0.25, "recall": 0.5, "f1": 1 / 3},
            {"tp": 2, "fp": 1, "fn": 1, "precision": 2 / 3, "recall": 2 / 3, "f1": 2 / 3},
        )
        self.assertEqual(delta["tp"], 1)
        self.assertEqual(delta["fp"], -2)
        self.assertEqual(delta["fn"], -1)
        self.assertAlmostEqual(delta["f1"], 1 / 3)

    def test_paired_change_categories(self):
        changes = paired_detection_changes(
            self.references, self.no_context, self.with_context
        )
        self.assertEqual(
            [(item["string_id"], item["issue_type"]) for item in changes["context_fixes"]],
            [("S1", "keigo_mismatch")],
        )
        self.assertEqual(
            [
                (item["string_id"], item["issue_type"])
                for item in changes["context_regressions"]
            ],
            [("S2", "first_person_mismatch")],
        )
        self.assertEqual(
            [
                (item["string_id"], item["issue_type"])
                for item in changes["new_false_positives"]
            ],
            [("S4", "character_voice_mismatch")],
        )
        self.assertEqual(
            [
                (item["string_id"], item["issue_type"])
                for item in changes["resolved_false_positives"]
            ],
            [("S3", "mistranslation")],
        )
    def test_context_sensitive_subset_and_controlled_config(self):
        comparison = compare_context_experiments(
            self.references,
            self.no_context,
            self.with_context,
            self.no_evaluation,
            self.with_evaluation,
            config("without_context"),
            config("with_context"),
        )
        self.assertEqual(
            set(comparison["context_sensitive_subset"]["issue_types"]),
            CONTEXT_SENSITIVE_ISSUES,
        )
        self.assertEqual(
            comparison["context_sensitive_subset"]["no_context"]["tp"], 1
        )
        self.assertEqual(
            comparison["context_sensitive_subset"]["with_context"]["tp"], 1
        )
        self.assertEqual(
            comparison["controlled_experiment_check"]["unintended_differences"],
            [],
        )
        per_issue = {
            row["issue_type"]: row for row in comparison["per_issue"]
        }
        self.assertEqual(per_issue["keigo_mismatch"]["delta"]["tp"], 1)
        self.assertEqual(
            per_issue["first_person_mismatch"]["delta"]["tp"], -1
        )
