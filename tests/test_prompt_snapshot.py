import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from j_gamelqa.io import load_glossary
from j_gamelqa.prompt_snapshot import (
    DEMO_RECORD,
    build_snapshot_prompts,
    render_prompt_snapshot,
    write_prompt_snapshot,
)
from j_gamelqa.prompts import (
    CONTEXT_INPUT_FIELDS,
    LLMInputMode,
    build_evaluator_prompt,
    build_llm_input,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class PromptSnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.glossary = load_glossary(PROJECT_ROOT / "data" / "glossary.csv")

    def test_snapshot_prompts_are_generated_by_real_builder(self):
        prompts = build_snapshot_prompts(self.glossary)
        self.assertEqual(
            prompts["without_context"],
            build_evaluator_prompt(
                DEMO_RECORD, self.glossary, LLMInputMode.WITHOUT_CONTEXT
            ),
        )
        self.assertEqual(
            prompts["with_context"],
            build_evaluator_prompt(
                DEMO_RECORD, self.glossary, LLMInputMode.WITH_CONTEXT
            ),
        )

    def test_committed_snapshot_matches_real_builder_output(self):
        self.assertEqual(
            (PROJECT_ROOT / "docs" / "prompt_v1_snapshot.md").read_text(
                encoding="utf-8"
            ),
            render_prompt_snapshot(self.glossary),
        )

    def test_context_modes_differ_only_by_six_expected_input_fields(self):
        without_context = build_llm_input(
            DEMO_RECORD, self.glossary, LLMInputMode.WITHOUT_CONTEXT
        )
        with_context = build_llm_input(
            DEMO_RECORD, self.glossary, LLMInputMode.WITH_CONTEXT
        )
        for field, value in without_context.items():
            self.assertEqual(with_context[field], value)
        self.assertEqual(
            set(with_context) - set(without_context),
            set(CONTEXT_INPUT_FIELDS),
        )

    @patch("urllib.request.urlopen")
    def test_snapshot_generation_does_not_call_provider(self, urlopen):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "snapshot.md"
            write_prompt_snapshot(
                destination,
                PROJECT_ROOT / "data" / "glossary.csv",
            )
            urlopen.assert_not_called()
            self.assertEqual(
                destination.read_text(encoding="utf-8"),
                render_prompt_snapshot(self.glossary),
            )


if __name__ == "__main__":
    unittest.main()
