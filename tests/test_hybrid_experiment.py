import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from j_gamelqa.evaluate import evaluate_detections
from j_gamelqa.hybrid import merge_hybrid_predictions
from j_gamelqa.hybrid_experiment import (
    artifact_paths,
    build_method_comparison,
    build_paired_analysis,
    run_artifact_experiment,
)
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


def issue(string_id, issue_type, checker):
    return Issue(
        string_id=string_id,
        checker=checker,
        issue_type=issue_type,
        severity="major",
        message="test",
        needs_human_review=checker == "japanese_llm",
    )


def reference_frame():
    return pd.DataFrame(
        [
            ("A1", "S1", "number_missing", "major", "", "", "{}", "test"),
            ("A2", "S2", "keigo_mismatch", "major", "", "", "{}", "test"),
            ("A3", "S3", "translationese", "minor", "", "", "{}", "test"),
        ],
        columns=REFERENCE_COLUMNS,
    )


def dev_frame():
    return pd.DataFrame(
        [
            {
                "string_id": string_id,
                "source_zh": "测试文本",
                "target_ja": "テスト文",
                "string_type": "dialogue",
                "speaker": "角色甲",
                "addressee": "角色乙",
                "scene": "测试场景",
                "relationship": "同伴",
                "context_before": "前文",
                "context_after": "后文",
                "max_length": "20",
            }
            for string_id in ("S1", "S2", "S3", "S4", "S5", "S6", "S9")
        ]
    )


class HybridComparisonTests(unittest.TestCase):
    def setUp(self):
        self.references = reference_frame()
        self.dev = dev_frame()
        self.rules = [
            issue("S1", "number_missing", "number"),
            issue("S4", "number_extra", "number"),
        ]
        self.no_context = []
        self.with_context = [
            issue("S2", "keigo_mismatch", "japanese_llm"),
            issue("S2", "keigo_mismatch", "japanese_llm"),
            issue("S5", "omission", "japanese_llm"),
            issue("S6", "number_mismatch", "japanese_llm"),
            issue("S9", "unregistered_issue", "japanese_llm"),
        ]
        self.merged = merge_hybrid_predictions(self.rules, self.with_context)

    def test_paired_fixes_and_false_positive_sources(self):
        result = build_paired_analysis(
            self.references,
            self.rules,
            self.with_context,
            self.merged,
        )
        self.assertEqual(
            [(row["string_id"], row["issue_type"]) for row in result["fixed_by_rule"]],
            [("S1", "number_missing")],
        )
        self.assertEqual(
            [(row["string_id"], row["issue_type"]) for row in result["fixed_by_llm"]],
            [("S2", "keigo_mismatch")],
        )
        sources = {
            (row["string_id"], row["issue_type"]): row["source_component"]
            for row in result["hybrid_false_positives"]
        }
        self.assertEqual(sources[("S4", "number_extra")], "rule")
        self.assertEqual(sources[("S5", "omission")], "llm")

    def test_four_method_and_scope_comparisons_use_shared_metrics(self):
        comparison, evaluations = build_method_comparison(
            self.references,
            self.dev,
            {
                "rule_only": self.rules,
                "llm_no_context": self.no_context,
                "llm_with_context": self.with_context,
                "hybrid": self.merged.predictions,
            },
        )
        self.assertEqual(evaluations["hybrid"]["overall_micro"]["tp"], 2)
        self.assertEqual(comparison["rule_addressable"]["hybrid"]["tp"], 1)
        self.assertEqual(comparison["llm_required"]["hybrid"]["tp"], 1)
        self.assertEqual(comparison["context_sensitive"]["hybrid"]["tp"], 1)
        self.assertEqual(
            comparison["pairwise"]["hybrid_vs_rule"]["overall"]["tp"],
            1,
        )
        self.assertEqual(len(comparison["per_issue"]), 22)


class ArtifactOnlyHybridTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.inputs = self.root / "inputs"
        self.outputs = self.root / "outputs"
        self.inputs.mkdir()
        self.references = reference_frame()
        self.dev = dev_frame()
        self.rules = [
            issue("S1", "number_missing", "number"),
            issue("S4", "number_extra", "number"),
        ]
        self.no_context = []
        self.with_context = [
            issue("S2", "keigo_mismatch", "japanese_llm"),
            issue("S2", "keigo_mismatch", "japanese_llm"),
            issue("S5", "omission", "japanese_llm"),
            issue("S6", "number_mismatch", "japanese_llm"),
            issue("S9", "unregistered_issue", "japanese_llm"),
        ]
        self.dev_path = self.inputs / "dev.csv"
        self.annotations_path = self.inputs / "annotations.csv"
        self.dev.to_csv(self.dev_path, index=False)
        self.references.to_csv(self.annotations_path, index=False)

        self.rule_predictions_path = self._write_predictions("rule.json", self.rules)
        self.no_predictions_path = self._write_predictions("no.json", self.no_context)
        self.with_predictions_path = self._write_predictions(
            "with.json", self.with_context
        )
        self.rule_evaluation_path = self._write_evaluation(
            "rule_eval.json", self.rules
        )
        self.no_evaluation_path = self._write_evaluation(
            "no_eval.json", self.no_context
        )
        self.with_evaluation_path = self._write_evaluation(
            "with_eval.json", self.with_context
        )
        self.with_config_path = self.inputs / "with_config.json"
        self.with_config_path.write_text(
            json.dumps(
                {
                    "experiment_id": "qwen35_9b_with_context_v1",
                    "model": "qwen3.5:9b",
                    "input_mode": "with_context",
                    "dataset": "test benchmark",
                    "dataset_item_count": 7,
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self):
        self.temporary_directory.cleanup()

    def _write_predictions(self, name, predictions):
        path = self.inputs / name
        path.write_text(
            json.dumps([prediction.to_dict() for prediction in predictions]),
            encoding="utf-8",
        )
        return path

    def _write_evaluation(self, name, predictions):
        path = self.inputs / name
        payload = evaluate_detections(self.references, predictions, self.dev)
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def kwargs(self):
        return {
            "dev_path": self.dev_path,
            "annotations_path": self.annotations_path,
            "rule_predictions_path": self.rule_predictions_path,
            "rule_evaluation_path": self.rule_evaluation_path,
            "llm_no_context_predictions_path": self.no_predictions_path,
            "llm_no_context_evaluation_path": self.no_evaluation_path,
            "llm_with_context_predictions_path": self.with_predictions_path,
            "llm_with_context_evaluation_path": self.with_evaluation_path,
            "llm_with_context_config_path": self.with_config_path,
            "output_dir": self.outputs,
        }

    @patch("urllib.request.urlopen")
    def test_runner_reads_artifacts_without_provider_call(self, urlopen):
        merge_result, evaluation, comparison, paths = run_artifact_experiment(
            **self.kwargs()
        )
        urlopen.assert_not_called()
        self.assertEqual(len(merge_result.predictions), 5)
        self.assertEqual(evaluation["merge_diagnostics"]["llm_predictions_excluded"], 2)
        self.assertEqual(evaluation["merge_diagnostics"]["excluded_unknown_count"], 1)
        self.assertEqual(
            evaluation["merge_diagnostics"]["excluded_rule_addressable_count"],
            1,
        )
        self.assertEqual(evaluation["duplicate_predictions"][0]["count"], 2)
        self.assertEqual(comparison["experiment"]["provider_calls"], 0)
        self.assertTrue(all(path.is_file() for path in paths.values()))

    def test_existing_artifact_is_never_overwritten(self):
        self.outputs.mkdir()
        protected = artifact_paths(self.outputs)["config"]
        protected.write_text("sealed", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            run_artifact_experiment(**self.kwargs())
        self.assertEqual(protected.read_text(encoding="utf-8"), "sealed")


if __name__ == "__main__":
    unittest.main()
