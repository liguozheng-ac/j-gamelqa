import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from j_gamelqa.evaluate import evaluate_detections
from j_gamelqa.llm_experiment import (
    artifact_paths,
    calculate_protocol_metrics,
    run_inference,
)
from j_gamelqa.prompts import LLMInputMode
from j_gamelqa.providers.ollama import (
    OllamaGeneration,
    OllamaProviderError,
)


REFERENCE_COLUMNS = (
    "annotation_id",
    "string_id",
    "issue_type",
    "severity",
    "source_span",
    "target_span",
    "evidence",
    "annotation_note",
)


def dev_frame():
    return pd.DataFrame(
        [
            {
                "string_id": "DEV_TEST",
                "source_zh": "队长，请您过目。",
                "target_ja": "隊長、見てくれ。",
                "string_type": "dialogue",
                "speaker": "新兵",
                "addressee": "队长",
                "scene": "指挥帐篷",
                "relationship": "部下与直属上级",
                "context_before": "报告已经送到。",
                "context_after": "队长接过报告。",
                "max_length": "80",
            }
        ]
    )


def raw_response(issue_type="keigo_mismatch"):
    return json.dumps(
        {
            "string_id": "DEV_TEST",
            "issues": [
                {
                    "issue_type": issue_type,
                    "severity": "major",
                    "source_span": "请您过目",
                    "target_span": "見てくれ",
                    "evidence": "The target uses an overly casual request.",
                }
            ],
        },
        ensure_ascii=False,
    )


def generation(response_text):
    return OllamaGeneration(
        raw_response=response_text,
        latency_seconds=1.25,
        model="qwen3.5:9b",
        done=True,
        done_reason="stop",
        thinking="",
        total_duration=1,
        load_duration=1,
        prompt_eval_count=10,
        prompt_eval_duration=1,
        eval_count=10,
        eval_duration=1,
    )


class FakeProvider:
    def __init__(self, response_text=None, failure=None):
        self.response_text = response_text
        self.failure = failure
        self.prompts = []

    def generate(self, prompt):
        self.prompts.append(prompt)
        if self.failure:
            raise self.failure
        return generation(self.response_text)


class LLMExperimentTests(unittest.TestCase):
    def run_one(self, provider, mode=LLMInputMode.WITHOUT_CONTEXT):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        raw_path = Path(directory.name) / "raw.jsonl"
        result = run_inference(
            dev_frame(),
            [],
            provider,
            raw_path,
            mode=mode,
            progress=None,
        )
        raw_records = [
            json.loads(line)
            for line in raw_path.read_text(encoding="utf-8").splitlines()
        ]
        return result, raw_records

    def test_runner_uses_without_context_prompt_and_no_annotations(self):
        provider = FakeProvider(raw_response())
        with patch(
            "j_gamelqa.llm_experiment.load_reference_annotations"
        ) as annotation_loader:
            self.run_one(provider)
        annotation_loader.assert_not_called()
        prompt = provider.prompts[0]
        for field in (
            "speaker",
            "addressee",
            "scene",
            "relationship",
            "context_before",
            "context_after",
        ):
            self.assertNotIn(f'"{field}"', prompt)

    def test_success_keeps_raw_response_and_converts_issue(self):
        expected_raw = raw_response()
        result, records = self.run_one(FakeProvider(expected_raw))
        self.assertEqual(records[0]["raw_response"], expected_raw)
        self.assertEqual(records[0]["protocol_status"], "success")
        self.assertEqual(len(result.predictions), 1)
        self.assertEqual(result.predictions[0].issue_type, "keigo_mismatch")

    def test_with_context_runner_includes_all_six_context_fields(self):
        provider = FakeProvider(raw_response())
        with patch(
            "j_gamelqa.llm_experiment.load_reference_annotations"
        ) as annotation_loader:
            self.run_one(provider, LLMInputMode.WITH_CONTEXT)
        annotation_loader.assert_not_called()
        prompt = provider.prompts[0]
        for field in (
            "speaker",
            "addressee",
            "scene",
            "relationship",
            "context_before",
            "context_after",
        ):
            self.assertIn(f'"{field}"', prompt)

    def test_context_artifact_names_cannot_overlap_sealed_baseline(self):
        no_context = set(
            artifact_paths("outputs", "qwen35_9b_no_context").values()
        )
        with_context = set(
            artifact_paths("outputs", "qwen35_9b_with_context").values()
        )
        self.assertTrue(no_context.isdisjoint(with_context))

    def test_protocol_failure_is_not_converted_to_clean(self):
        result, records = self.run_one(FakeProvider("not json"))
        self.assertEqual(result.predictions, [])
        self.assertEqual(records[0]["provider_status"], "success")
        self.assertEqual(records[0]["protocol_status"], "parse_failure")
        self.assertTrue(
            records[0]["protocol_diagnostics"]["parse_failures"]
        )

    def test_provider_failure_has_zero_predictions_and_runtime_diagnostic(self):
        result, records = self.run_one(
            FakeProvider(
                failure=OllamaProviderError(
                    "connection_error", "service unavailable"
                )
            )
        )
        self.assertEqual(result.predictions, [])
        self.assertEqual(records[0]["provider_status"], "failure")
        self.assertEqual(records[0]["protocol_status"], "not_run")
        self.assertEqual(
            records[0]["provider_error"]["category"], "connection_error"
        )

    def test_protocol_failure_naturally_becomes_false_negative(self):
        result, records = self.run_one(FakeProvider("not json"))
        references = pd.DataFrame(
            [
                (
                    "A1",
                    "DEV_TEST",
                    "keigo_mismatch",
                    "major",
                    "",
                    "",
                    "{}",
                    "test",
                )
            ],
            columns=REFERENCE_COLUMNS,
        )
        evaluation = evaluate_detections(references, result.predictions)
        metrics = calculate_protocol_metrics(
            records, result.predictions
        )
        self.assertEqual(evaluation["overall_micro"]["fn"], 1)
        self.assertEqual(metrics["parse_failures"], 1)
        self.assertEqual(metrics["protocol_success_rate"], 0.0)

    def test_protocol_metrics_count_success_and_predictions(self):
        result, records = self.run_one(FakeProvider(raw_response()))
        metrics = calculate_protocol_metrics(records, result.predictions)
        self.assertEqual(metrics["total_requests"], 1)
        self.assertEqual(metrics["successful_provider_calls"], 1)
        self.assertEqual(metrics["provider_failures"], 0)
        self.assertEqual(metrics["protocol_success_rate"], 1.0)
        self.assertEqual(metrics["raw_prediction_count"], 1)
        self.assertEqual(metrics["unique_prediction_detection_count"], 1)
        self.assertEqual(metrics["mean_latency_seconds"], 1.25)
