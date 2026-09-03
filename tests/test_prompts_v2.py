import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from j_gamelqa.io import load_glossary
from j_gamelqa.prompt_snapshot import DEMO_RECORD, build_snapshot_prompts
from j_gamelqa.prompt_v2_snapshot import (
    build_v2_snapshot_prompts,
    render_prompt_v2_snapshot,
    write_prompt_v2_snapshot,
)
from j_gamelqa.prompts import CONTEXT_INPUT_FIELDS, LLMInputMode, build_evaluator_prompt
from j_gamelqa.prompts_v2 import build_evaluator_prompt_v2
from j_gamelqa.taxonomy import ISSUE_TYPE_DEFINITIONS


PROJECT_ROOT = Path(__file__).resolve().parents[1]
V1_WITHOUT_HASH = "F36162A11642FF070F1EBCBE4A04AA1B82864FEFCC61AE23117BF0F6A495218A"
V1_WITH_HASH = "11635FC05B3ED316F65978C4575C049787498E453094369937D8FF2E7B5CD906"


def text_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest().upper()


class PromptV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.glossary = load_glossary(PROJECT_ROOT / "data" / "glossary.csv")

    def test_prompt_v1_frozen_hashes_are_unchanged(self):
        prompts = build_snapshot_prompts(self.glossary)
        self.assertEqual(text_hash(prompts["without_context"]), V1_WITHOUT_HASH)
        self.assertEqual(text_hash(prompts["with_context"]), V1_WITH_HASH)

    def test_prompt_v2_is_independent_and_does_not_change_v1(self):
        v1_before = build_evaluator_prompt(
            DEMO_RECORD, self.glossary, LLMInputMode.WITH_CONTEXT
        )
        v2 = build_evaluator_prompt_v2(
            DEMO_RECORD, self.glossary, LLMInputMode.WITH_CONTEXT
        )
        v1_after = build_evaluator_prompt(
            DEMO_RECORD, self.glossary, LLMInputMode.WITH_CONTEXT
        )
        self.assertEqual(v1_before, v1_after)
        self.assertNotEqual(v1_before, v2)
        self.assertIn("Taxonomy boundary guidance", v2)

    def test_output_contract_is_byte_identical_to_prompt_v1(self):
        v1 = build_evaluator_prompt(
            DEMO_RECORD, self.glossary, LLMInputMode.WITH_CONTEXT
        )
        v2 = build_evaluator_prompt_v2(
            DEMO_RECORD, self.glossary, LLMInputMode.WITH_CONTEXT
        )
        marker = "Required JSON contract\n"
        self.assertEqual(v1.split(marker, 1)[1], v2.split(marker, 1)[1])

    def test_taxonomy_still_comes_from_single_source_of_truth(self):
        prompt = build_evaluator_prompt_v2(
            DEMO_RECORD, self.glossary, LLMInputMode.WITH_CONTEXT
        )
        for issue_type, definition in ISSUE_TYPE_DEFINITIONS.items():
            self.assertIn(f"- {issue_type}: {definition}", prompt)

    def test_v2_context_modes_follow_existing_field_policy(self):
        without_context = build_evaluator_prompt_v2(
            DEMO_RECORD, self.glossary, LLMInputMode.WITHOUT_CONTEXT
        )
        with_context = build_evaluator_prompt_v2(
            DEMO_RECORD, self.glossary, LLMInputMode.WITH_CONTEXT
        )
        for field in CONTEXT_INPUT_FIELDS:
            self.assertNotIn(f'"{field}"', without_context)
            self.assertIn(f'"{field}"', with_context)

    @patch("urllib.request.urlopen")
    def test_v2_snapshot_uses_real_builder_and_no_test_sample(self, urlopen):
        prompts = build_v2_snapshot_prompts(self.glossary)
        self.assertEqual(
            prompts["with_context"],
            build_evaluator_prompt_v2(
                DEMO_RECORD, self.glossary, LLMInputMode.WITH_CONTEXT
            ),
        )
        rendered = render_prompt_v2_snapshot(self.glossary)
        self.assertNotIn("TEST_", rendered)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "v2.md"
            write_prompt_v2_snapshot(path, PROJECT_ROOT / "data" / "glossary.csv")
            self.assertEqual(path.read_text(encoding="utf-8"), rendered)
        urlopen.assert_not_called()

    def test_committed_v2_snapshot_matches_real_builder(self):
        snapshot = PROJECT_ROOT / "docs" / "prompt_v2_snapshot.md"
        self.assertEqual(
            snapshot.read_text(encoding="utf-8"),
            render_prompt_v2_snapshot(self.glossary),
        )


if __name__ == "__main__":
    unittest.main()
