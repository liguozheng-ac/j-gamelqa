import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from j_gamelqa.llm_experiment import artifact_paths
from j_gamelqa.llm_prompt_v2_experiment import (
    ARTIFACT_PREFIX,
    _validate_development_identity,
    run_v2_inference,
)
from j_gamelqa.providers.ollama import OllamaGeneration


def record(string_id="DEV_001"):
    return {
        "string_id": string_id,
        "source_zh": "队长，请确认。",
        "target_ja": "隊長、ご確認ください。",
        "string_type": "dialogue",
        "speaker": "队员",
        "addressee": "队长",
        "scene": "营地",
        "relationship": "队员向队长报告",
        "context_before": "装置已经修好。",
        "context_after": "队长走向装置。",
        "max_length": "40",
    }


class FakeProvider:
    def __init__(self):
        self.prompts = []

    def generate(self, prompt):
        self.prompts.append(prompt)
        return OllamaGeneration(
            raw_response=json.dumps({"string_id": "DEV_001", "issues": []}),
            latency_seconds=0.1,
            model="qwen3.5:9b",
            done=True,
            done_reason="stop",
            thinking="",
            total_duration=1,
            load_duration=1,
            prompt_eval_count=1,
            prompt_eval_duration=1,
            eval_count=1,
            eval_duration=1,
        )


class PromptV2ExperimentTests(unittest.TestCase):
    @patch("j_gamelqa.io.load_test_dataset")
    def test_inference_uses_dev_record_and_never_test_loader(self, test_loader):
        provider = FakeProvider()
        with tempfile.TemporaryDirectory() as directory:
            result = run_v2_inference(
                pd.DataFrame([record()]),
                [],
                provider,
                Path(directory) / "raw.jsonl",
                progress=None,
            )
        test_loader.assert_not_called()
        self.assertEqual(result.predictions, [])
        self.assertIn("Taxonomy boundary guidance", provider.prompts[0])
        self.assertIn('"context_before"', provider.prompts[0])

    def test_formal_identity_guard_rejects_test_or_partial_data(self):
        with self.assertRaisesRegex(ValueError, "Development Set"):
            _validate_development_identity(pd.DataFrame([record("TEST_001")]))

    def test_v2_artifact_names_are_disjoint_from_v1(self):
        v1 = set(artifact_paths("outputs", "qwen35_9b_with_context").values())
        v2 = set(artifact_paths("outputs", ARTIFACT_PREFIX).values())
        self.assertTrue(v1.isdisjoint(v2))


if __name__ == "__main__":
    unittest.main()
