import tempfile
import unittest
from pathlib import Path

from j_gamelqa.io import load_dataset, load_glossary


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class InputLoadingTests(unittest.TestCase):
    def test_load_pilot_dataset(self):
        frame = load_dataset(PROJECT_ROOT / "data" / "pilot.csv")
        self.assertEqual(len(frame), 10)
        self.assertIn("source_zh", frame.columns)

    def test_missing_dataset_field_raises(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "broken.csv"
            path.write_text("string_id,source_zh\nA,测试\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing required fields"):
                load_dataset(path)

    def test_load_glossary(self):
        glossary = load_glossary(PROJECT_ROOT / "data" / "glossary.csv")
        self.assertGreaterEqual(len(glossary), 1)
        self.assertEqual(set(glossary[0]), {"source_term", "approved_ja", "forbidden_ja"})
