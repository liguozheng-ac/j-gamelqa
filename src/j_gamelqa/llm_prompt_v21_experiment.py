"""Single-run Qwen3.5-9B Prompt v2.1 experiment on Development only."""

import argparse
import hashlib
import json
from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Callable

import pandas as pd

from j_gamelqa.evaluate import evaluate_detections
from j_gamelqa.io import load_dev_dataset, load_glossary, load_reference_annotations
from j_gamelqa.llm_evaluator import parse_llm_response
from j_gamelqa.llm_experiment import (
    ExperimentConfig,
    InferenceResult,
    _append_raw_record,
    _bad_cases_with_raw,
    _protocol_status,
    _provider_metadata,
    _write_json,
    artifact_paths,
    calculate_protocol_metrics,
)
from j_gamelqa.prompts import CONTEXT_INPUT_FIELDS, LLMInputMode
from j_gamelqa.prompts_v21 import PROMPT_VERSION, build_evaluator_prompt_v21
from j_gamelqa.providers.ollama import OllamaProvider, OllamaProviderError


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_ID = "qwen35_9b_with_context_prompt_v21_dev_v1"
ARTIFACT_PREFIX = "qwen35_9b_with_context_prompt_v21_dev"
MODEL = "qwen3.5:9b"
TIMEOUT_SECONDS = 120.0


def _sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest().upper()


def _validate_development_identity(dev_frame: pd.DataFrame) -> None:
    expected_ids = {f"DEV_{number:03d}" for number in range(1, 49)}
    actual_ids = set(dev_frame["string_id"])
    if len(dev_frame) != 48 or actual_ids != expected_ids:
        raise ValueError(
            "Prompt v2.1 experiment accepts only the frozen 48-item Development Set"
        )


def run_v21_inference(
    dev_frame: pd.DataFrame,
    glossary: list[dict[str, str]],
    provider: OllamaProvider,
    raw_path: str | Path,
    *,
    progress: Callable[[str], None] | None = print,
) -> InferenceResult:
    """Run Prompt v2.1 WITH_CONTEXT inference without loading annotations."""
    checkpoint_path = Path(raw_path)
    if checkpoint_path.exists():
        raise FileExistsError(
            f"Prompt v2.1 raw artifact already exists: {checkpoint_path}"
        )

    raw_records = []
    predictions = []
    total = len(dev_frame)
    for index, record in enumerate(dev_frame.to_dict(orient="records"), start=1):
        string_id = str(record["string_id"])
        prompt = build_evaluator_prompt_v21(
            record,
            glossary,
            LLMInputMode.WITH_CONTEXT,
        )
        context_fields = {
            field for field in CONTEXT_INPUT_FIELDS if f'"{field}"' in prompt
        }
        if context_fields != set(CONTEXT_INPUT_FIELDS):
            raise RuntimeError("Prompt v2.1 WITH_CONTEXT input is missing context fields")

        started = perf_counter()
        try:
            generation = provider.generate(prompt)
        except OllamaProviderError as exc:
            raw_record = {
                "string_id": string_id,
                "provider_status": "failure",
                "provider_error": {
                    "category": exc.category,
                    "message": str(exc),
                },
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
                f"[{index}/{total}] {string_id}: "
                f"{raw_record['provider_status']}/{raw_record['protocol_status']} "
                f"{raw_record['latency_seconds']:.3f}s"
            )

    return InferenceResult(raw_records=raw_records, predictions=predictions)


def run_v21_development_experiment(
    *,
    dev_path: str | Path,
    glossary_path: str | Path,
    annotations_path: str | Path,
    output_dir: str | Path,
    provider: OllamaProvider,
    progress: Callable[[str], None] | None = print,
) -> tuple[InferenceResult, dict, dict[str, Path]]:
    """Persist one non-overwriting Prompt v2.1 Development experiment."""
    paths = artifact_paths(output_dir, ARTIFACT_PREFIX)
    existing = [path for path in paths.values() if path.exists()]
    if existing:
        raise FileExistsError(
            "Prompt v2.1 Development artifacts already exist and will not be "
            "overwritten: " + ", ".join(str(path) for path in existing)
        )

    dev_frame = load_dev_dataset(dev_path)
    _validate_development_identity(dev_frame)
    glossary = load_glossary(glossary_path)
    config = replace(
        ExperimentConfig(),
        experiment_id=EXPERIMENT_ID,
        input_mode=LLMInputMode.WITH_CONTEXT.value,
        prompt_version=PROMPT_VERSION,
    )
    config_payload = {
        **asdict(config),
        "created_at_utc": datetime.now(UTC).isoformat(),
        "development_only": True,
        "formal_run_policy": "single_run_no_retry_no_repair",
        "prompt_builder": "j_gamelqa.prompts_v21.build_evaluator_prompt_v21",
        "candidate_gate_version": "stage_7b1_pre_registered_v1",
        "dev_path": str(Path(dev_path).resolve()),
        "dev_sha256": _sha256(dev_path),
        "glossary_path": str(Path(glossary_path).resolve()),
        "glossary_sha256": _sha256(glossary_path),
        "annotations_path_for_evaluation_only": str(Path(annotations_path).resolve()),
        "annotations_sha256": _sha256(annotations_path),
    }
    _write_json(paths["config"], config_payload)

    inference = run_v21_inference(
        dev_frame,
        glossary,
        provider,
        paths["raw"],
        progress=progress,
    )
    if len(inference.raw_records) != 48:
        raise RuntimeError("Prompt v2.1 Development inference is incomplete")

    _write_json(
        paths["predictions"],
        [prediction.to_dict() for prediction in inference.predictions],
    )
    references = load_reference_annotations(annotations_path, dev_frame)
    evaluation = evaluate_detections(references, inference.predictions, dev_frame)
    evaluation["experiment_id"] = EXPERIMENT_ID
    evaluation["protocol_metrics"] = calculate_protocol_metrics(
        inference.raw_records,
        inference.predictions,
    )
    _write_json(paths["evaluation"], evaluation)
    _write_json(paths["bad_cases"], _bad_cases_with_raw(evaluation, inference.raw_records))
    return inference, evaluation, paths


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the single Prompt v2.1 experiment on frozen Development."
    )
    parser.add_argument(
        "--output-dir", type=Path, default=PROJECT_ROOT / "outputs"
    )
    args = parser.parse_args()
    provider = OllamaProvider(
        MODEL,
        timeout_seconds=TIMEOUT_SECONDS,
        temperature=0,
        thinking=False,
        stream=False,
    )
    inference, evaluation, paths = run_v21_development_experiment(
        dev_path=PROJECT_ROOT / "data" / "dev.csv",
        glossary_path=PROJECT_ROOT / "data" / "glossary.csv",
        annotations_path=PROJECT_ROOT / "data" / "dev_annotations.csv",
        output_dir=args.output_dir,
        provider=provider,
    )
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "dataset": "Development Set",
                "raw_prediction_count": len(inference.predictions),
                "overall_micro": evaluation["overall_micro"],
                "llm_required_micro": evaluation["llm_required_micro"],
                "protocol_metrics": evaluation["protocol_metrics"],
                "artifacts": {name: str(path) for name, path in paths.items()},
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
