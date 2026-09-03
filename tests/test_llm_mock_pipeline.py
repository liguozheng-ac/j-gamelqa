import json
import unittest
from pathlib import Path

from j_gamelqa.evaluate import evaluate_detections
from j_gamelqa.hybrid import merge_hybrid_predictions
from j_gamelqa.io import (
    load_dev_dataset,
    load_glossary,
    load_reference_annotations,
)
from j_gamelqa.llm_evaluator import run_llm_evaluator
from j_gamelqa.prompts import LLMInputMode
from j_gamelqa.rule_engine import evaluate_record


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def fake_provider(payload):
    raw_response = json.dumps(payload, ensure_ascii=False)

    def generate(_prompt):
        return raw_response

    return generate


def llm_issue(issue_type, severity="major", source_span="", target_span=""):
    return {
        "issue_type": issue_type,
        "severity": severity,
        "source_span": source_span,
        "target_span": target_span,
        "evidence": f"Mock QA evidence for {issue_type}.",
    }


class MockEndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dev = load_dev_dataset(PROJECT_ROOT / "data" / "dev.csv")
        cls.annotations = load_reference_annotations(
            PROJECT_ROOT / "data" / "dev_annotations.csv", cls.dev
        )
        cls.glossary = load_glossary(PROJECT_ROOT / "data" / "glossary.csv")

    def record(self, string_id):
        return (
            self.dev.loc[self.dev["string_id"] == string_id]
            .iloc[0]
            .to_dict()
        )

    def references(self, string_id):
        return self.annotations.loc[
            self.annotations["string_id"] == string_id
        ].copy()

    def test_mock_clean_pipeline_produces_no_issue_objects(self):
        record = self.record("DEV_011")
        run = run_llm_evaluator(
            record,
            self.glossary,
            LLMInputMode.WITHOUT_CONTEXT,
            fake_provider({"string_id": "DEV_011", "issues": []}),
        )
        self.assertTrue(run.result.is_valid)
        self.assertEqual(run.result.predictions, [])
        self.assertIn("DEV_011", run.prompt)

    def test_mock_llm_required_issue_reaches_evaluation_harness(self):
        record = self.record("DEV_008")
        run = run_llm_evaluator(
            record,
            self.glossary,
            LLMInputMode.WITH_CONTEXT,
            fake_provider(
                {
                    "string_id": "DEV_008",
                    "issues": [
                        llm_issue(
                            "keigo_mismatch",
                            target_span="見てくれ",
                        )
                    ],
                }
            ),
        )
        evaluation = evaluate_detections(
            self.references("DEV_008"), run.result.predictions
        )
        self.assertEqual(evaluation["overall_micro"]["tp"], 1)
        self.assertEqual(evaluation["overall_micro"]["fp"], 0)

    def test_mock_multi_issue_llm_only_and_hybrid_paths(self):
        record = self.record("DEV_040")
        run = run_llm_evaluator(
            record,
            self.glossary,
            LLMInputMode.WITH_CONTEXT,
            fake_provider(
                {
                    "string_id": "DEV_040",
                    "issues": [
                        llm_issue("number_mismatch", target_span="5"),
                        llm_issue("keigo_mismatch", target_span="命令を出せ"),
                    ],
                }
            ),
        )

        llm_only = evaluate_detections(
            self.references("DEV_040"), run.result.predictions
        )
        self.assertEqual(llm_only["overall_micro"]["tp"], 2)

        rule_predictions = evaluate_record(record, self.glossary)
        hybrid = merge_hybrid_predictions(
            rule_predictions, run.result.predictions
        )
        self.assertEqual(
            [issue.issue_type for issue in hybrid.predictions],
            ["number_mismatch", "keigo_mismatch"],
        )
        self.assertEqual(
            [
                issue.issue_type
                for issue in hybrid.llm_predictions_excluded_from_hybrid
            ],
            ["number_mismatch"],
        )
        hybrid_evaluation = evaluate_detections(
            self.references("DEV_040"), hybrid.predictions
        )
        self.assertEqual(hybrid_evaluation["overall_micro"]["tp"], 2)
