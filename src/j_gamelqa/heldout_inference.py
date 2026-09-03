"""Prediction-only held-out runner; it never accepts or loads annotations."""

import argparse
import hashlib
import json
from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Callable

import pandas as pd

from j_gamelqa.io import load_glossary, load_test_dataset
from j_gamelqa.llm_evaluator import parse_llm_response
from j_gamelqa.llm_experiment import (
    ExperimentConfig,
    InferenceResult,
    _append_raw_record,
    _protocol_status,
    _provider_metadata,
    _write_json,
    calculate_protocol_metrics,
)
from j_gamelqa.models import Issue
from j_gamelqa.prompts import CONTEXT_INPUT_FIELDS, LLMInputMode, build_evaluator_prompt
from j_gamelqa.prompts_v21 import build_evaluator_prompt_v21
from j_gamelqa.providers.ollama import OllamaProvider, OllamaProviderError
from j_gamelqa.rule_engine import evaluate_dataframe


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODEL = "qwen3.5:9b"
TIMEOUT_SECONDS = 120.0
TEST_DATASET_NAME = "60-item synthetic held-out Test Set v1"

CANDIDATES = {
    "prompt-v1": {
        "experiment_id": "test_qwen35_prompt_v1_with_context_v1",
        "prompt_version": "v1",
        "builder": build_evaluator_prompt,
        "builder_name": "j_gamelqa.prompts.build_evaluator_prompt",
        "prefix": "test_qwen35_prompt_v1",
    },
    "prompt-v21": {
        "experiment_id": "test_qwen35_prompt_v21_with_context_v1",
        "prompt_version": "v2.1",
        "builder": build_evaluator_prompt_v21,
        "builder_name": "j_gamelqa.prompts_v21.build_evaluator_prompt_v21",
        "prefix": "test_qwen35_prompt_v21",
    },
}


def sha256_file(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest().upper()


def _validate_test_identity(test_frame: pd.DataFrame) -> None:
    expected_ids = {f"TEST_{number:03d}" for number in range(1, 61)}
    if len(test_frame) != 60 or set(test_frame["string_id"]) != expected_ids:
        raise ValueError("held-out runner accepts only the frozen 60-item Test Set")


def run_rule_prediction_phase(
    test_path: str | Path,
    glossary_path: str | Path,
    output_path: str | Path,
) -> list[Issue]:
    destination = Path(output_path)
    if destination.exists():
        raise FileExistsError(f"Rule Test predictions already exist: {destination}")
    test_frame = load_test_dataset(test_path)
    _validate_test_identity(test_frame)
    glossary = load_glossary(glossary_path)
    predictions = evaluate_dataframe(test_frame, glossary)
    _write_json(destination, [item.to_dict() for item in predictions])
    return predictions


def candidate_artifact_paths(
    output_dir: str | Path, candidate: str
) -> dict[str, Path]:
    prefix = CANDIDATES[candidate]["prefix"]
    destination = Path(output_dir)
    return {
        "config": destination / f"{prefix}_config.json",
        "raw": destination / f"{prefix}_raw.jsonl",
        "predictions": destination / f"{prefix}_predictions.json",
    }


def run_candidate_prediction_phase(
    test_frame: pd.DataFrame,
    glossary: list[dict[str, str]],
    provider: OllamaProvider,
    raw_path: str | Path,
    *,
    candidate: str,
    progress: Callable[[str], None] | None = print,
) -> InferenceResult:
    """Generate one candidate's predictions without annotation access."""
    _validate_test_identity(test_frame)
    checkpoint_path = Path(raw_path)
    if checkpoint_path.exists():
        raise FileExistsError(f"Held-out raw artifact already exists: {checkpoint_path}")
    builder = CANDIDATES[candidate]["builder"]
    raw_records = []
    predictions = []
    for index, record in enumerate(test_frame.to_dict(orient="records"), start=1):
        string_id = str(record["string_id"])
        prompt = builder(record, glossary, LLMInputMode.WITH_CONTEXT)
        context_fields = {
            field for field in CONTEXT_INPUT_FIELDS if f'"{field}"' in prompt
        }
        if context_fields != set(CONTEXT_INPUT_FIELDS):
            raise RuntimeError("held-out With Context prompt is missing context fields")
        started = perf_counter()
        try:
            generation = provider.generate(prompt)
        except OllamaProviderError as exc:
            raw_record = {
                "string_id": string_id,
                "provider_status": "failure",
                "provider_error": {"category": exc.category, "message": str(exc)},
                "protocol_status": "not_run",
                "raw_response": None,
                "latency_seconds": perf_counter() - started,
                "provider_metadata": None,
                "protocol_diagnostics": None,
                "prediction_count": 0,
            }
        else:
            parsed = parse_llm_response(generation.raw_response, string_id)
            diagnostics = parsed.diagnostics.to_dict()
            predictions.extend(parsed.predictions)
            raw_record = {
                "string_id": string_id,
                "provider_status": "success",
                "provider_error": None,
                "protocol_status": _protocol_status(diagnostics),
                "raw_response": generation.raw_response,
                "latency_seconds": generation.latency_seconds,
                "provider_metadata": _provider_metadata(generation),
                "protocol_diagnostics": diagnostics,
                "prediction_count": len(parsed.predictions),
            }
        _append_raw_record(checkpoint_path, raw_record)
        raw_records.append(raw_record)
        if progress:
            progress(
                f"[{index}/60] {string_id}: "
                f"{raw_record['provider_status']}/{raw_record['protocol_status']} "
                f"{raw_record['latency_seconds']:.3f}s"
            )
    return InferenceResult(raw_records=raw_records, predictions=predictions)


def run_llm_prediction_phase(
    *,
    candidate: str,
    test_path: str | Path,
    glossary_path: str | Path,
    output_dir: str | Path,
    provider: OllamaProvider,
    progress: Callable[[str], None] | None = print,
) -> tuple[InferenceResult, dict[str, Path]]:
    paths = candidate_artifact_paths(output_dir, candidate)
    existing = [path for path in paths.values() if path.exists()]
    if existing:
        raise FileExistsError(
            "Held-out candidate artifacts already exist: "
            + ", ".join(str(path) for path in existing)
        )
    test_frame = load_test_dataset(test_path)
    _validate_test_identity(test_frame)
    glossary = load_glossary(glossary_path)
    spec = CANDIDATES[candidate]
    config = replace(
        ExperimentConfig(),
        experiment_id=spec["experiment_id"],
        input_mode=LLMInputMode.WITH_CONTEXT.value,
        prompt_version=spec["prompt_version"],
        dataset=TEST_DATASET_NAME,
        dataset_item_count=60,
    )
    _write_json(
        paths["config"],
        {
            **asdict(config),
            "created_at_utc": datetime.now(UTC).isoformat(),
            "held_out_final_evaluation": True,
            "prediction_phase_only": True,
            "annotation_path_accepted": False,
            "formal_run_policy": "single_run_no_retry_no_repair",
            "prompt_builder": spec["builder_name"],
            "test_path": str(Path(test_path).resolve()),
            "test_sha256": sha256_file(test_path),
            "glossary_path": str(Path(glossary_path).resolve()),
            "glossary_sha256": sha256_file(glossary_path),
        },
    )
    inference = run_candidate_prediction_phase(
        test_frame,
        glossary,
        provider,
        paths["raw"],
        candidate=candidate,
        progress=progress,
    )
    if len(inference.raw_records) != 60:
        raise RuntimeError("held-out candidate inference is incomplete")
    _write_json(
        paths["predictions"], [item.to_dict() for item in inference.predictions]
    )
    return inference, paths


def _read_raw_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def freeze_prediction_artifacts(output_dir: str | Path) -> Path:
    output = Path(output_dir)
    destination = output / "heldout_prediction_freeze.json"
    if destination.exists():
        raise FileExistsError(f"prediction freeze already exists: {destination}")
    files = {
        "rule_predictions": output / "test_rule_predictions.json",
        "prompt_v1_config": output / "test_qwen35_prompt_v1_config.json",
        "prompt_v1_raw": output / "test_qwen35_prompt_v1_raw.jsonl",
        "prompt_v1_predictions": output / "test_qwen35_prompt_v1_predictions.json",
        "prompt_v21_config": output / "test_qwen35_prompt_v21_config.json",
        "prompt_v21_raw": output / "test_qwen35_prompt_v21_raw.jsonl",
        "prompt_v21_predictions": output / "test_qwen35_prompt_v21_predictions.json",
    }
    missing = [str(path) for path in files.values() if not path.exists()]
    if missing:
        raise FileNotFoundError("prediction artifacts are incomplete: " + ", ".join(missing))
    protocol = {}
    for candidate in ("prompt_v1", "prompt_v21"):
        records = _read_raw_jsonl(files[f"{candidate}_raw"])
        if len(records) != 60:
            raise RuntimeError(f"{candidate} does not contain 60 raw records")
        failures = [row for row in records if row["provider_status"] != "success"]
        if failures:
            raise RuntimeError(
                f"{candidate} has provider failures; keep artifacts and stop evaluation"
            )
        predictions = json.loads(files[f"{candidate}_predictions"].read_text(encoding="utf-8"))
        protocol[candidate] = {
            "raw_records": len(records),
            "provider_failures": 0,
            "raw_prediction_count": len(predictions),
            "protocol_metrics": calculate_protocol_metrics(records, [Issue(**row) for row in predictions]),
        }
    payload = {
        "freeze_id": "heldout_prediction_freeze_v1",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "annotations_loaded": False,
        "status": "all_predictions_frozen_before_evaluation",
        "artifact_sha256": {name: sha256_file(path) for name, path in files.items()},
        "protocol": protocol,
    }
    _write_json(destination, payload)
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description="Run held-out prediction-only phases.")
    parser.add_argument(
        "phase", choices=("rule", "prompt-v1", "prompt-v21", "freeze-predictions")
    )
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "outputs")
    args = parser.parse_args()
    if args.phase == "rule":
        predictions = run_rule_prediction_phase(
            PROJECT_ROOT / "data" / "test.csv",
            PROJECT_ROOT / "data" / "glossary.csv",
            args.output_dir / "test_rule_predictions.json",
        )
        print(json.dumps({"phase": "rule", "predictions": len(predictions)}, indent=2))
        return
    if args.phase == "freeze-predictions":
        print(freeze_prediction_artifacts(args.output_dir))
        return
    provider = OllamaProvider(
        MODEL,
        timeout_seconds=TIMEOUT_SECONDS,
        temperature=0,
        thinking=False,
        stream=False,
    )
    inference, paths = run_llm_prediction_phase(
        candidate=args.phase,
        test_path=PROJECT_ROOT / "data" / "test.csv",
        glossary_path=PROJECT_ROOT / "data" / "glossary.csv",
        output_dir=args.output_dir,
        provider=provider,
    )
    print(
        json.dumps(
            {
                "phase": args.phase,
                "requests": len(inference.raw_records),
                "predictions": len(inference.predictions),
                "artifacts": {name: str(path) for name, path in paths.items()},
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
