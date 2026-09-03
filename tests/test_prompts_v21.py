import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from j_gamelqa.io import load_glossary
from j_gamelqa.prompt_snapshot import DEMO_RECORD, build_snapshot_prompts
from j_gamelqa.prompt_v2_snapshot import build_v2_snapshot_prompts
from j_gamelqa.prompt_v21_snapshot import (
    build_v21_snapshot_prompts,
    render_prompt_v21_snapshot,
    write_prompt_v21_snapshot,
)
from j_gamelqa.prompts import CONTEXT_INPUT_FIELDS, LLMInputMode, build_evaluator_prompt
from j_gamelqa.prompts_v21 import build_evaluator_prompt_v21
from j_gamelqa.taxonomy import ISSUE_TYPE_DEFINITIONS


PROJECT_ROOT = Path(__file__).resolve().parents[1]
V1_WITHOUT_HASH = "F36162A11642FF070F1EBCBE4A04AA1B82864FEFCC61AE23117BF0F6A495218A"
V1_WITH_HASH = "11635FC05B3ED316F65978C4575C049787498E453094369937D8FF2E7B5CD906"
V2_WITHOUT_HASH = "80FC3A6CECE2656692D787E738F09004A930745B751740F1B40C449D88B80559"
V2_WITH_HASH = "7E7FB852E6B00E67914758F97DE38D15DF5DF7F392AE46294CA38083650FB932"


def text_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest().upper()


class PromptV21Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.glossary = load_glossary(PROJECT_ROOT / "data" / "glossary.csv")

    def test_v1_and_v2_rendered_hashes_remain_frozen(self):
        v1 = build_snapshot_prompts(self.glossary)
        v2 = build_v2_snapshot_prompts(self.glossary)
        self.assertEqual(text_hash(v1["without_context"]), V1_WITHOUT_HASH)
        self.assertEqual(text_hash(v1["with_context"]), V1_WITH_HASH)
        self.assertEqual(text_hash(v2["without_context"]), V2_WITHOUT_HASH)
        self.assertEqual(text_hash(v2["with_context"]), V2_WITH_HASH)

    def test_v21_is_independent_and_minimal(self):
        prompt = build_evaluator_prompt_v21(
            DEMO_RECORD, self.glossary, LLMInputMode.WITH_CONTEXT
        )
        v1 = build_evaluator_prompt(
            DEMO_RECORD, self.glossary, LLMInputMode.WITH_CONTEXT
        )
        v2 = build_v2_snapshot_prompts(self.glossary)["with_context"]
        self.assertNotEqual(prompt, v1)
        self.assertNotEqual(prompt, v2)
        self.assertIn("Minimal evaluation guidance", prompt)
        self.assertNotIn("Final consistency rules", prompt)
        self.assertNotIn("Natural explicitation", prompt)
        self.assertNotIn("Prefer a specific supported type", prompt)

    def test_output_contract_is_byte_identical_to_v1(self):
        v1 = build_evaluator_prompt(
            DEMO_RECORD, self.glossary, LLMInputMode.WITH_CONTEXT
        )
        v21 = build_evaluator_prompt_v21(
            DEMO_RECORD, self.glossary, LLMInputMode.WITH_CONTEXT
        )
        marker = "Required JSON contract\n"
        self.assertEqual(v1.split(marker, 1)[1], v21.split(marker, 1)[1])

    def test_taxonomy_still_comes_from_single_source(self):
        prompt = build_evaluator_prompt_v21(
            DEMO_RECORD, self.glossary, LLMInputMode.WITH_CONTEXT
        )
        for issue_type, definition in ISSUE_TYPE_DEFINITIONS.items():
            self.assertIn(f"- {issue_type}: {definition}", prompt)

    def test_context_field_policy_is_unchanged(self):
        without_context = build_evaluator_prompt_v21(
            DEMO_RECORD, self.glossary, LLMInputMode.WITHOUT_CONTEXT
        )
        with_context = build_evaluator_prompt_v21(
            DEMO_RECORD, self.glossary, LLMInputMode.WITH_CONTEXT
        )
        for field in CONTEXT_INPUT_FIELDS:
            self.assertNotIn(f'"{field}"', without_context)
            self.assertIn(f'"{field}"', with_context)

    @patch("urllib.request.urlopen")
    def test_snapshot_uses_real_builder_and_not_test(self, urlopen):
        prompts = build_v21_snapshot_prompts(self.glossary)
        self.assertEqual(
            prompts["with_context"],
            build_evaluator_prompt_v21(
                DEMO_RECORD, self.glossary, LLMInputMode.WITH_CONTEXT
            ),
        )
        rendered = render_prompt_v21_snapshot(self.glossary)
        self.assertNotIn("TEST_", rendered)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "v21.md"
            write_prompt_v21_snapshot(
                path, PROJECT_ROOT / "data" / "glossary.csv"
            )
            self.assertEqual(path.read_text(encoding="utf-8"), rendered)
        urlopen.assert_not_called()

    def test_committed_snapshot_matches_real_builder(self):
        self.assertEqual(
            (PROJECT_ROOT / "docs" / "prompt_v21_snapshot.md").read_text(
                encoding="utf-8"
            ),
            render_prompt_v21_snapshot(self.glossary),
        )


if __name__ == "__main__":
    unittest.main()
