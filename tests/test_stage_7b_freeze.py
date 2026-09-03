import hashlib
import json
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


class Stage7BFreezeTests(unittest.TestCase):
    def test_v1_artifacts_and_contracts_match_freeze_manifest(self):
        manifest_path = PROJECT_ROOT / "outputs" / "v1_experiment_freeze_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for relative_path, expected_hash in manifest["artifact_sha256"].items():
            self.assertEqual(
                sha256(PROJECT_ROOT / "outputs" / relative_path),
                expected_hash,
                relative_path,
            )
        for relative_path, expected_hash in manifest[
            "input_and_contract_sha256"
        ].items():
            self.assertEqual(
                sha256(PROJECT_ROOT / relative_path),
                expected_hash,
                relative_path,
            )

    def test_held_out_test_files_match_frozen_manifest_hashes(self):
        manifest = json.loads(
            (PROJECT_ROOT / "data" / "benchmark_manifest.json").read_text(
                encoding="utf-8"
            )
        )
        expected = manifest["held_out_test"]["sha256"]
        self.assertEqual(sha256(PROJECT_ROOT / "data" / "test.csv"), expected["test.csv"])
        self.assertEqual(
            sha256(PROJECT_ROOT / "data" / "test_annotations.csv"),
            expected["test_annotations.csv"],
        )


if __name__ == "__main__":
    unittest.main()
