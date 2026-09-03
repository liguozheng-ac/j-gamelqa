import tempfile
import unittest
from collections import Counter
from pathlib import Path

import pandas as pd

from j_gamelqa.io import load_dev_dataset, load_reference_annotations
from j_gamelqa.taxonomy import (
    LLM_REQUIRED_ISSUE_TYPES,
    REGISTERED_ISSUE_TYPES,
    RULE_ADDRESSABLE_ISSUE_TYPES,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class BenchmarkInputTests(unittest.TestCase):
    def setUp(self):
        self.dev_path = PROJECT_ROOT / "data" / "dev.csv"
        self.annotations_path = PROJECT_ROOT / "data" / "dev_annotations.csv"
        self.dev_frame = load_dev_dataset(self.dev_path)

    def _write_frame(self, frame, name):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / name
        frame.to_csv(path, index=False)
        return path

    def test_valid_dev_dataset_and_annotations_load(self):
        annotations = load_reference_annotations(
            self.annotations_path, self.dev_frame
        )
        self.assertEqual(len(self.dev_frame), 48)
        self.assertEqual(len(annotations), 51)
        self.assertNotIn("expected_issue", self.dev_frame.columns)

    def test_dev_ids_are_complete_and_unique(self):
        expected_ids = {f"DEV_{number:03d}" for number in range(1, 49)}
        actual_ids = set(self.dev_frame["string_id"])
        self.assertEqual(actual_ids, expected_ids)
        self.assertEqual(len(actual_ids), len(self.dev_frame))

    def test_reference_taxonomy_has_required_coverage(self):
        annotations = load_reference_annotations(
            self.annotations_path, self.dev_frame
        )
        type_counts = Counter(annotations["issue_type"])
        annotated_types = set(type_counts)
        self.assertTrue(annotated_types <= REGISTERED_ISSUE_TYPES)
        self.assertTrue(RULE_ADDRESSABLE_ISSUE_TYPES <= annotated_types)
        self.assertTrue(LLM_REQUIRED_ISSUE_TYPES <= annotated_types)
        self.assertTrue(
            all(type_counts[issue_type] >= 1 for issue_type in RULE_ADDRESSABLE_ISSUE_TYPES)
        )
        self.assertTrue(
            all(type_counts[issue_type] >= 2 for issue_type in LLM_REQUIRED_ISSUE_TYPES)
        )

    def test_benchmark_has_clean_and_multi_issue_samples(self):
        annotations = load_reference_annotations(
            self.annotations_path, self.dev_frame
        )
        counts = Counter(annotations["string_id"])
        clean_ids = set(self.dev_frame["string_id"]) - set(counts)
        multi_issue_ids = {string_id for string_id, count in counts.items() if count >= 2}
        self.assertGreaterEqual(len(clean_ids), 1)
        self.assertGreaterEqual(len(multi_issue_ids), 8)

    def test_missing_dev_required_column_fails(self):
        broken = self.dev_frame.drop(columns=["target_ja"])
        with self.assertRaisesRegex(ValueError, "missing required fields: target_ja"):
            load_dev_dataset(self._write_frame(broken, "dev.csv"))

    def test_annotation_unknown_string_id_fails(self):
        annotations = pd.read_csv(self.annotations_path, dtype=str, keep_default_na=False)
        annotations.loc[0, "string_id"] = "DEV_999"
        with self.assertRaisesRegex(ValueError, "missing from dev dataset: DEV_999"):
            load_reference_annotations(
                self._write_frame(annotations, "annotations.csv"), self.dev_frame
            )

    def test_duplicate_annotation_id_fails(self):
        annotations = pd.read_csv(self.annotations_path, dtype=str, keep_default_na=False)
        duplicate = annotations.iloc[[0]].copy()
        duplicate.loc[:, "string_id"] = "DEV_003"
        annotations = pd.concat([annotations, duplicate], ignore_index=True)
        with self.assertRaisesRegex(ValueError, "duplicate annotation_id"):
            load_reference_annotations(
                self._write_frame(annotations, "annotations.csv"), self.dev_frame
            )

    def test_duplicate_reference_detection_key_fails(self):
        annotations = pd.read_csv(self.annotations_path, dtype=str, keep_default_na=False)
        duplicate = annotations.iloc[[0]].copy()
        duplicate.loc[:, "annotation_id"] = "ANN_DUP"
        annotations = pd.concat([annotations, duplicate], ignore_index=True)
        with self.assertRaisesRegex(ValueError, "duplicate detection keys"):
            load_reference_annotations(
                self._write_frame(annotations, "annotations.csv"), self.dev_frame
            )

    def test_unknown_reference_issue_type_fails(self):
        annotations = pd.read_csv(self.annotations_path, dtype=str, keep_default_na=False)
        annotations.loc[0, "issue_type"] = "magic_wrong_translation_v3"
        with self.assertRaisesRegex(
            ValueError, "unknown reference issue_type.*magic_wrong_translation_v3"
        ):
            load_reference_annotations(
                self._write_frame(annotations, "annotations.csv"), self.dev_frame
            )

    def test_reference_annotation_can_be_absent_for_clean_sample(self):
        annotations = load_reference_annotations(
            self.annotations_path, self.dev_frame
        )
        self.assertNotIn("DEV_001", set(annotations["string_id"]))
