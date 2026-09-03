import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from j_gamelqa.benchmark_freeze import (
    check_split_leakage,
    validate_benchmark_splits,
)
from j_gamelqa.io import (
    ANSWER_LEAKAGE_FIELDS,
    DEV_INPUT_FIELDS,
    REFERENCE_ANNOTATION_FIELDS,
    load_dev_dataset,
    load_reference_annotations,
    load_test_dataset,
)
from j_gamelqa.taxonomy import (
    LLM_REQUIRED_ISSUE_TYPES,
    REGISTERED_ISSUE_TYPES,
    RULE_ADDRESSABLE_ISSUE_TYPES,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class HeldOutBenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dev = load_dev_dataset(PROJECT_ROOT / "data" / "dev.csv")
        cls.test = load_test_dataset(PROJECT_ROOT / "data" / "test.csv")
        cls.annotations = load_reference_annotations(
            PROJECT_ROOT / "data" / "test_annotations.csv",
            cls.test,
        )

    def test_test_input_schema_count_ids_and_no_answer_leakage(self):
        self.assertEqual(tuple(self.test.columns), DEV_INPUT_FIELDS)
        self.assertEqual(len(self.test), 60)
        self.assertEqual(
            set(self.test["string_id"]),
            {f"TEST_{number:03d}" for number in range(1, 61)},
        )
        self.assertFalse(self.test["string_id"].duplicated().any())
        self.assertFalse(ANSWER_LEAKAGE_FIELDS.intersection(self.test.columns))

    def test_annotation_schema_keys_and_registered_taxonomy(self):
        self.assertEqual(tuple(self.annotations.columns), REFERENCE_ANNOTATION_FIELDS)
        self.assertFalse(self.annotations["annotation_id"].duplicated().any())
        self.assertFalse(
            self.annotations.duplicated(subset=["string_id", "issue_type"]).any()
        )
        self.assertEqual(set(self.annotations["issue_type"]), REGISTERED_ISSUE_TYPES)

    def test_reference_coverage_targets(self):
        counts = Counter(self.annotations["issue_type"])
        self.assertTrue(
            all(counts[issue_type] >= 2 for issue_type in RULE_ADDRESSABLE_ISSUE_TYPES)
        )
        self.assertTrue(
            all(counts[issue_type] >= 4 for issue_type in LLM_REQUIRED_ISSUE_TYPES)
        )

    def test_composition_targets(self):
        counts = Counter(self.annotations["string_id"])
        clean = set(self.test["string_id"]) - set(counts)
        single = {key for key, count in counts.items() if count == 1}
        multi = {key for key, count in counts.items() if count >= 2}
        self.assertEqual((len(clean), len(single), len(multi)), (10, 34, 16))
        self.assertEqual(len(self.annotations), 66)

    def test_manifest_context_and_hard_negative_targets(self):
        import json

        manifest = json.loads(
            (PROJECT_ROOT / "data" / "benchmark_manifest.json").read_text(
                encoding="utf-8"
            )
        )["held_out_test"]
        self.assertGreaterEqual(len(manifest["hard_negative_ids"]), 10)
        self.assertGreaterEqual(len(manifest["context_sensitive_ids"]), 15)

    def test_real_splits_have_no_exact_or_normalized_duplicates(self):
        leakage = check_split_leakage(self.dev, self.test)
        self.assertEqual(leakage["exact_duplicates"], [])
        self.assertEqual(leakage["normalized_duplicates"], [])

    def test_exact_duplicate_check_detects_cross_split_match(self):
        development = pd.DataFrame(
            [{"string_id": "DEV_X", "source_zh": "相同", "target_ja": "別", "context_before": "甲", "context_after": "乙"}]
        )
        held_out = pd.DataFrame(
            [{"string_id": "TEST_X", "source_zh": "相同", "target_ja": "他", "context_before": "丙", "context_after": "丁"}]
        )
        leakage = check_split_leakage(development, held_out)
        self.assertEqual(len(leakage["exact_duplicates"]), 1)

    def test_normalized_duplicate_check_detects_width_case_and_whitespace(self):
        development = pd.DataFrame(
            [{"string_id": "DEV_X", "source_zh": "Alpha", "target_ja": "別", "context_before": "甲", "context_after": "乙"}]
        )
        held_out = pd.DataFrame(
            [{"string_id": "TEST_X", "source_zh": "  ＡＬＰＨＡ  ", "target_ja": "他", "context_before": "丙", "context_after": "丁"}]
        )
        leakage = check_split_leakage(development, held_out)
        self.assertEqual(leakage["exact_duplicates"], [])
        self.assertEqual(len(leakage["normalized_duplicates"]), 1)

    @patch("urllib.request.urlopen")
    def test_static_validation_does_not_call_provider(self, urlopen):
        result = validate_benchmark_splits(
            dev_path=PROJECT_ROOT / "data" / "dev.csv",
            dev_annotations_path=PROJECT_ROOT / "data" / "dev_annotations.csv",
            test_path=PROJECT_ROOT / "data" / "test.csv",
            test_annotations_path=PROJECT_ROOT / "data" / "test_annotations.csv",
            manifest_path=PROJECT_ROOT / "data" / "benchmark_manifest.json",
        )
        urlopen.assert_not_called()
        self.assertTrue(result["static_validation_only"])
        self.assertEqual(result["provider_calls"], 0)

    def test_stage_7c_predictions_have_a_pre_annotation_freeze(self):
        import hashlib
        import json

        freeze = json.loads(
            (PROJECT_ROOT / "outputs" / "heldout_prediction_freeze.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertFalse(freeze["annotations_loaded"])
        paths = {
            "rule_predictions": "test_rule_predictions.json",
            "prompt_v1_config": "test_qwen35_prompt_v1_config.json",
            "prompt_v1_raw": "test_qwen35_prompt_v1_raw.jsonl",
            "prompt_v1_predictions": "test_qwen35_prompt_v1_predictions.json",
            "prompt_v21_config": "test_qwen35_prompt_v21_config.json",
            "prompt_v21_raw": "test_qwen35_prompt_v21_raw.jsonl",
            "prompt_v21_predictions": "test_qwen35_prompt_v21_predictions.json",
        }
        for key, name in paths.items():
            actual = hashlib.sha256(
                (PROJECT_ROOT / "outputs" / name).read_bytes()
            ).hexdigest().upper()
            self.assertEqual(actual, freeze["artifact_sha256"][key], name)


if __name__ == "__main__":
    unittest.main()
