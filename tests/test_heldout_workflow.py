import inspect
import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from j_gamelqa.heldout_analysis import (
    clean_false_alarm_metrics,
    multi_issue_metrics,
)
from j_gamelqa.heldout_freeze import PROTOCOL_SHA256
from j_gamelqa.heldout_inference import (
    _validate_test_identity,
    candidate_artifact_paths,
    run_candidate_prediction_phase,
    run_llm_prediction_phase,
    run_rule_prediction_phase,
)
from j_gamelqa.models import Issue
from j_gamelqa.providers.ollama import OllamaGeneration


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def record(string_id):
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


def issue(string_id, issue_type):
    return Issue(
        string_id=string_id,
        checker="test",
        issue_type=issue_type,
        severity="major",
        message="test",
    )


class FakeProvider:
    def __init__(self):
        self.index = 0

    def generate(self, prompt):
        self.index += 1
        return OllamaGeneration(
            raw_response=json.dumps(
                {"string_id": f"TEST_{self.index:03d}", "issues": []}
            ),
            latency_seconds=0.01,
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


class HeldOutWorkflowTests(unittest.TestCase):
    def test_stored_preflight_was_frozen_without_loading_annotations(self):
        payload = json.loads(
            (
                PROJECT_ROOT / "outputs" / "heldout_pre_evaluation_freeze.json"
            ).read_text(encoding="utf-8")
        )
        self.assertFalse(payload["annotation_content_loaded"])
        self.assertEqual(payload["protocol_sha256"], PROTOCOL_SHA256)

    def test_generation_functions_have_no_annotation_parameter(self):
        for function in (
            run_rule_prediction_phase,
            run_candidate_prediction_phase,
            run_llm_prediction_phase,
        ):
            self.assertNotIn("annotations_path", inspect.signature(function).parameters)

    def test_test_identity_guard(self):
        valid = pd.DataFrame(
            [record(f"TEST_{number:03d}") for number in range(1, 61)]
        )
        _validate_test_identity(valid)
        with self.assertRaisesRegex(ValueError, "Test Set"):
            _validate_test_identity(pd.DataFrame([record("DEV_001")]))

    def test_candidate_outputs_are_independent(self):
        v1 = set(candidate_artifact_paths("outputs", "prompt-v1").values())
        v21 = set(candidate_artifact_paths("outputs", "prompt-v21").values())
        self.assertTrue(v1.isdisjoint(v21))

    def test_fake_provider_exercises_60_record_prediction_phase(self):
        frame = pd.DataFrame(
            [record(f"TEST_{number:03d}") for number in range(1, 61)]
        )
        provider = FakeProvider()
        with tempfile.TemporaryDirectory() as directory:
            result = run_candidate_prediction_phase(
                frame,
                [],
                provider,
                Path(directory) / "raw.jsonl",
                candidate="prompt-v1",
                progress=None,
            )
        self.assertEqual(len(result.raw_records), 60)
        self.assertEqual(provider.index, 60)

    def test_clean_false_alarm_is_sample_level(self):
        frame = pd.DataFrame({"string_id": ["C1", "C2", "E1"]})
        references = pd.DataFrame(
            [{"string_id": "E1", "issue_type": "mistranslation"}]
        )
        result = clean_false_alarm_metrics(
            frame,
            references,
            {"method": [issue("C1", "omission"), issue("C1", "addition")]},
        )
        self.assertEqual(result["clean_sample_count"], 2)
        self.assertEqual(
            result["methods"]["method"]["false_alarmed_clean_samples"], 1
        )
        self.assertEqual(result["methods"]["method"]["false_alarm_rate"], 0.5)

    def test_multi_issue_full_partial_and_missed(self):
        references = pd.DataFrame(
            [
                {"string_id": "M1", "issue_type": "omission"},
                {"string_id": "M1", "issue_type": "mistranslation"},
                {"string_id": "M2", "issue_type": "addition"},
                {"string_id": "M2", "issue_type": "translationese"},
                {"string_id": "M3", "issue_type": "keigo_mismatch"},
                {"string_id": "M3", "issue_type": "character_voice_mismatch"},
            ]
        )
        predictions = [
            issue("M1", "omission"),
            issue("M1", "mistranslation"),
            issue("M2", "addition"),
        ]
        result = multi_issue_metrics(references, {"method": predictions})["methods"][
            "method"
        ]
        self.assertEqual(result["fully_detected"], 1)
        self.assertEqual(result["partially_detected"], 1)
        self.assertEqual(result["completely_missed"], 1)


if __name__ == "__main__":
    unittest.main()
