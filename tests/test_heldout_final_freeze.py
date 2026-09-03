import hashlib
import json
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


class HeldOutFinalFreezeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(
            (
                PROJECT_ROOT
                / "outputs"
                / "heldout_evaluation_freeze_manifest.json"
            ).read_text(encoding="utf-8")
        )

    def test_final_status_and_test_hashes(self):
        self.assertEqual(
            self.manifest["status"], "first_and_final_heldout_result_frozen"
        )
        for name, expected in self.manifest["test_sha256"].items():
            self.assertEqual(sha256(PROJECT_ROOT / "data" / name), expected)

    def test_frozen_source_hashes_still_match(self):
        for relative_path, expected in self.manifest["source_sha256"].items():
            self.assertEqual(
                sha256(PROJECT_ROOT / relative_path), expected, relative_path
            )

    def test_prediction_evaluation_and_comparison_artifacts_match(self):
        for name, expected in self.manifest["result_artifact_sha256"].items():
            self.assertEqual(
                sha256(PROJECT_ROOT / "outputs" / name), expected, name
            )

    def test_protocol_hash_matches(self):
        self.assertEqual(
            sha256(PROJECT_ROOT / "docs" / "heldout_evaluation_protocol.md"),
            self.manifest["protocol_sha256"],
        )


if __name__ == "__main__":
    unittest.main()
