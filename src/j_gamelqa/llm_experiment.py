"""Reproducible Qwen3.5-9B context-control baseline runner."""

import argparse
import json
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean, median
from time import perf_counter
from typing import Callable

import pandas as pd

from j_gamelqa.evaluate import evaluate_detections
from j_gamelqa.io import (
    load_dev_dataset,
    load_glossary,
    load_reference_annotations,
)
from j_gamelqa.llm_evaluator import parse_llm_response
from j_gamelqa.models import Issue
from j_gamelqa.prompts import (
    CONTEXT_INPUT_FIELDS,
    LLMInputMode,
    build_evaluator_prompt,
)
from j_gamelqa.providers.ollama import (
    OllamaGeneration,
    OllamaProvider,
    OllamaProviderError,
)
from j_gamelqa.taxonomy import REGISTERED_ISSUE_TYPES


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_ID = "qwen35_9b_no_context_v1"
WITH_CONTEXT_EXPERIMENT_ID = "qwen35_9b_with_context_v1"
MODEL = "qwen3.5:9b"
TIMEOUT_SECONDS = 120.0
PROMPT_VERSION = "v1"
DATASET_NAME = "48-item synthetic development benchmark v1"


@dataclass(frozen=True, slots=True)
class ExperimentConfig:
    experiment_id: str = EXPERIMENT_ID
    model: str = MODEL
    provider: str = "ollama"
    provider_endpoint: str = "http://127.0.0.1:11434/api/generate"
    input_mode: str = "without_context"
    temperature: float = 0.0
    thinking: bool = False
    stream: bool = False
    prompt_version: str = PROMPT_VERSION
    parser_policy: str = "stage_6a_strict_no_repair"
    retry_policy: str = "off"
    structured_output: bool = False
    timeout_seconds: float = TIMEOUT_SECONDS
    dataset: str = DATASET_NAME
    dataset_item_count: int = 48


@dataclass(slots=True)
class InferenceResult:
    raw_records: list[dict[str, object]]
    predictions: list[Issue]


def artifact_paths(
    output_dir: str | Path,
    prefix: str = "qwen35_9b_no_context",
) -> dict[str, Path]:
    destination = Path(output_dir)
    return {
        "config": destination / f"{prefix}_config.json",
        "raw": destination / f"{prefix}_raw.jsonl",
        "predictions": destination / f"{prefix}_predictions.json",
        "evaluation": destination / f"{prefix}_evaluation.json",
        "bad_cases": destination / f"{prefix}_bad_cases.json",
    }


def _protocol_status(diagnostics: dict[str, object]) -> str:
    if diagnostics["parse_failures"]:
        return "parse_failure"
    if diagnostics["schema_failures"]:
        return "schema_failure"
    if diagnostics["validation_failures"]:
        return "validation_failure"
    return "success"


def _provider_metadata(generation: OllamaGeneration) -> dict[str, object]:
    return {
        "model": generation.model,
        "done": generation.done,
        "done_reason": generation.done_reason,
        "thinking": generation.thinking,
        "total_duration": generation.total_duration,
        "load_duration": generation.load_duration,
        "prompt_eval_count": generation.prompt_eval_count,
        "prompt_eval_duration": generation.prompt_eval_duration,
        "eval_count": generation.eval_count,
        "eval_duration": generation.eval_duration,
    }


def _parse_record_predictions(raw_record: dict[str, object]) -> list[Issue]:
    if raw_record["provider_status"] != "success":
        return []
    parsed = parse_llm_response(
        str(raw_record["raw_response"]), str(raw_record["string_id"])
    )
    return parsed.predictions


def load_raw_checkpoint(path: str | Path) -> list[dict[str, object]]:
    checkpoint = Path(path)
    if not checkpoint.exists():
        return []
    records = []
    seen_ids = set()
    for line_number, line in enumerate(
        checkpoint.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"invalid raw checkpoint JSON at line {line_number}"
            ) from exc
        string_id = record.get("string_id")
        if not isinstance(string_id, str):
            raise ValueError(
                f"raw checkpoint line {line_number} has invalid string_id"
            )
        if string_id in seen_ids:
            raise ValueError(f"duplicate raw checkpoint string_id: {string_id}")
        seen_ids.add(string_id)
        records.append(record)
    return records


def _append_raw_record(path: Path, record: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")
        file.flush()


def run_inference(
    dev_frame: pd.DataFrame,
    glossary: list[dict[str, str]],
    provider: OllamaProvider,
    raw_path: str | Path,
    *,
    mode: LLMInputMode = LLMInputMode.WITHOUT_CONTEXT,
    resume: bool = False,
    progress: Callable[[str], None] | None = print,
) -> InferenceResult:
    """Run inference in the selected context mode without loading references."""
    checkpoint_path = Path(raw_path)
    if checkpoint_path.exists() and not resume:
        raise FileExistsError(
            f"raw baseline artifact already exists: {checkpoint_path}"
        )

    raw_records = load_raw_checkpoint(checkpoint_path) if resume else []
    known_ids = set(dev_frame["string_id"])
    checkpoint_ids = {str(record["string_id"]) for record in raw_records}
    unknown_checkpoint_ids = sorted(checkpoint_ids - known_ids)
    if unknown_checkpoint_ids:
        raise ValueError(
            "raw checkpoint contains IDs outside the dev dataset: "
            + ", ".join(unknown_checkpoint_ids)
        )
    predictions = [
        issue
        for record in raw_records
        for issue in _parse_record_predictions(record)
    ]

    total = len(dev_frame)
    for index, record in enumerate(
        dev_frame.to_dict(orient="records"), start=1
    ):
        string_id = str(record["string_id"])
        if string_id in checkpoint_ids:
            if progress:
                progress(f"[{index}/{total}] {string_id}: checkpoint")
            continue

        prompt = build_evaluator_prompt(record, glossary, mode)
        context_fields_in_prompt = [
            field for field in CONTEXT_INPUT_FIELDS if f'"{field}"' in prompt
        ]
        if mode is LLMInputMode.WITHOUT_CONTEXT and context_fields_in_prompt:
            raise RuntimeError(
                "WITHOUT_CONTEXT prompt contains context fields: "
                + ", ".join(context_fields_in_prompt)
            )
        if mode is LLMInputMode.WITH_CONTEXT and set(context_fields_in_prompt) != set(
            CONTEXT_INPUT_FIELDS
        ):
            missing_context_fields = sorted(
                set(CONTEXT_INPUT_FIELDS) - set(context_fields_in_prompt)
            )
            raise RuntimeError(
                "WITH_CONTEXT prompt is missing context fields: "
                + ", ".join(missing_context_fields)
            )

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
        checkpoint_ids.add(string_id)
        if progress:
            progress(
                f"[{index}/{total}] {string_id}: "
                f"{raw_record['provider_status']}/{raw_record['protocol_status']} "
                f"{raw_record['latency_seconds']:.3f}s"
            )

    return InferenceResult(raw_records=raw_records, predictions=predictions)


def calculate_protocol_metrics(
    raw_records: list[dict[str, object]], predictions: list[Issue]
) -> dict[str, object]:
    successful_calls = [
        record
        for record in raw_records
        if record["provider_status"] == "success"
    ]
    provider_failures = [
        record
        for record in raw_records
        if record["provider_status"] == "failure"
    ]
    protocol_successes = [
        record
        for record in successful_calls
        if record["protocol_status"] == "success"
    ]
    latencies = [
        float(record["latency_seconds"])
        for record in successful_calls
    ]
    diagnostics = [
        record["protocol_diagnostics"]
        for record in successful_calls
        if isinstance(record["protocol_diagnostics"], dict)
    ]
    unknown_types = sorted(
        {
            issue_type
            for diagnostic in diagnostics
            for issue_type in diagnostic["unknown_issue_types"]
        }
    )
    duplicate_predictions = [
        duplicate
        for diagnostic in diagnostics
        for duplicate in diagnostic["duplicate_predictions"]
    ]
    prediction_keys = {
        (prediction.string_id, prediction.issue_type)
        for prediction in predictions
    }
    return {
        "total_requests": len(raw_records),
        "successful_provider_calls": len(successful_calls),
        "provider_failures": len(provider_failures),
        "provider_failure_details": [
            {
                "string_id": record["string_id"],
                **record["provider_error"],
            }
            for record in provider_failures
        ],
        "protocol_successful_responses": len(protocol_successes),
        "parse_failures": sum(
            bool(diagnostic["parse_failures"]) for diagnostic in diagnostics
        ),
        "schema_failures": sum(
            bool(diagnostic["schema_failures"]) for diagnostic in diagnostics
        ),
        "validation_failures": sum(
            bool(diagnostic["validation_failures"]) for diagnostic in diagnostics
        ),
        "unknown_issue_types": unknown_types,
        "unknown_issue_type_count": len(unknown_types),
        "duplicate_predictions": duplicate_predictions,
        "duplicate_prediction_key_count": len(duplicate_predictions),
        "protocol_success_rate": (
            len(protocol_successes) / len(successful_calls)
            if successful_calls
            else 0.0
        ),
        "protocol_success_rate_denominator": "successful_provider_calls",
        "raw_prediction_count": len(predictions),
        "unique_prediction_detection_count": len(prediction_keys),
        "mean_latency_seconds": mean(latencies) if latencies else None,
        "median_latency_seconds": median(latencies) if latencies else None,
        "thinking_content_responses": sum(
            bool(record["provider_metadata"].get("thinking"))
            for record in successful_calls
            if isinstance(record["provider_metadata"], dict)
        ),
    }


def _bad_cases_with_raw(
    evaluation: dict, raw_records: list[dict[str, object]]
) -> dict[str, object]:
    raw_by_id = {
        str(record["string_id"]): record for record in raw_records
    }

    def enrich(case: dict) -> dict:
        raw = raw_by_id.get(str(case["string_id"]), {})
        return {
            **case,
            "provider_status": raw.get("provider_status"),
            "protocol_status": raw.get("protocol_status"),
            "raw_response": raw.get("raw_response"),
        }

    return {
        "false_positives": [
            enrich(case) for case in evaluation["false_positives"]
        ],
        "false_negatives": [
            enrich(case) for case in evaluation["false_negatives"]
        ],
    }


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def run_experiment(
    dev_path: str | Path,
    glossary_path: str | Path,
    annotations_path: str | Path,
    output_dir: str | Path,
    provider: OllamaProvider,
    *,
    mode: LLMInputMode = LLMInputMode.WITHOUT_CONTEXT,
    experiment_id: str = EXPERIMENT_ID,
    artifact_prefix: str = "qwen35_9b_no_context",
    resume: bool = False,
    progress: Callable[[str], None] | None = print,
) -> tuple[InferenceResult, dict, dict[str, Path]]:
    """Run and persist one fixed context-mode baseline without overwriting it."""
    paths = artifact_paths(output_dir, artifact_prefix)
    completed_outputs = [
        paths["predictions"], paths["evaluation"], paths["bad_cases"]
    ]
    if any(path.exists() for path in completed_outputs):
        raise FileExistsError(
            "completed baseline artifacts already exist and will not be overwritten"
        )
    if paths["config"].exists() and not resume:
        raise FileExistsError(
            f"baseline config already exists: {paths['config']}"
        )

    dev_frame = load_dev_dataset(dev_path)
    if len(dev_frame) != 48:
        raise ValueError(f"baseline requires exactly 48 dev items, got {len(dev_frame)}")
    glossary = load_glossary(glossary_path)
    config = replace(
        ExperimentConfig(),
        experiment_id=experiment_id,
        input_mode=mode.value,
    )
    config_payload = {
        **asdict(config),
        "created_at_utc": datetime.now(UTC).isoformat(),
        "dev_path": str(Path(dev_path).resolve()),
        "glossary_path": str(Path(glossary_path).resolve()),
        "annotations_path_for_evaluation_only": str(
            Path(annotations_path).resolve()
        ),
    }
    if not paths["config"].exists():
        _write_json(paths["config"], config_payload)

    inference = run_inference(
        dev_frame,
        glossary,
        provider,
        paths["raw"],
        mode=mode,
        resume=resume,
        progress=progress,
    )
    if len(inference.raw_records) != len(dev_frame):
        raise RuntimeError(
            "inference checkpoint is incomplete; resume before evaluation"
        )

    _write_json(
        paths["predictions"],
        [prediction.to_dict() for prediction in inference.predictions],
    )

    # Reference annotations enter only after all inference calls are complete.
    reference_annotations = load_reference_annotations(
        annotations_path, dev_frame
    )
    evaluation = evaluate_detections(
        reference_annotations, inference.predictions, dev_frame
    )
    evaluation["experiment_id"] = experiment_id
    evaluation["protocol_metrics"] = calculate_protocol_metrics(
        inference.raw_records, inference.predictions
    )
    _write_json(paths["evaluation"], evaluation)
    _write_json(
        paths["bad_cases"],
        _bad_cases_with_raw(evaluation, inference.raw_records),
    )
    return inference, evaluation, paths


def run_smoke_test(
    string_id: str,
    dev_path: str | Path,
    glossary_path: str | Path,
    provider: OllamaProvider,
    mode: LLMInputMode = LLMInputMode.WITHOUT_CONTEXT,
) -> dict[str, object]:
    """Call one real item without creating or changing baseline artifacts."""
    dev_frame = load_dev_dataset(dev_path)
    selected = dev_frame.loc[dev_frame["string_id"] == string_id]
    if len(selected) != 1:
        raise ValueError(f"smoke-test string_id not found: {string_id}")
    record = selected.iloc[0].to_dict()
    glossary = load_glossary(glossary_path)
    prompt = build_evaluator_prompt(record, glossary, mode)
    generation = provider.generate(prompt)
    parsed = parse_llm_response(generation.raw_response, string_id)
    return {
        "string_id": string_id,
        "input_mode": mode.value,
        "provider_status": "success",
        "protocol_status": _protocol_status(parsed.diagnostics.to_dict()),
        "latency_seconds": generation.latency_seconds,
        "thinking_content_present": bool(generation.thinking),
        "raw_response": generation.raw_response,
        "protocol_diagnostics": parsed.diagnostics.to_dict(),
        "prediction_count": len(parsed.predictions),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a fixed Qwen3.5-9B context-control baseline."
    )
    parser.add_argument("--model", choices=[MODEL], default=MODEL)
    parser.add_argument(
        "--mode",
        choices=["without-context", "with-context"],
        default="without-context",
    )
    parser.add_argument(
        "--dev", type=Path, default=PROJECT_ROOT / "data" / "dev.csv"
    )
    parser.add_argument(
        "--glossary",
        type=Path,
        default=PROJECT_ROOT / "data" / "glossary.csv",
    )
    parser.add_argument(
        "--annotations",
        type=Path,
        default=PROJECT_ROOT / "data" / "dev_annotations.csv",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=PROJECT_ROOT / "outputs"
    )
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--smoke-string-id")
    args = parser.parse_args()

    provider = OllamaProvider(
        args.model,
        timeout_seconds=TIMEOUT_SECONDS,
        temperature=0,
        thinking=False,
        stream=False,
    )
    if args.mode == "with-context":
        mode = LLMInputMode.WITH_CONTEXT
        experiment_id = WITH_CONTEXT_EXPERIMENT_ID
        artifact_prefix = "qwen35_9b_with_context"
    else:
        mode = LLMInputMode.WITHOUT_CONTEXT
        experiment_id = EXPERIMENT_ID
        artifact_prefix = "qwen35_9b_no_context"
    if args.smoke_string_id:
        print(
            json.dumps(
                run_smoke_test(
                    args.smoke_string_id,
                    args.dev,
                    args.glossary,
                    provider,
                    mode,
                ),
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    inference, evaluation, paths = run_experiment(
        args.dev,
        args.glossary,
        args.annotations,
        args.output_dir,
        provider,
        mode=mode,
        experiment_id=experiment_id,
        artifact_prefix=artifact_prefix,
        resume=args.resume,
    )
    print(
        json.dumps(
            {
                "experiment_id": experiment_id,
                "raw_prediction_count": len(inference.predictions),
                "overall_micro": evaluation["overall_micro"],
                "llm_required_micro": evaluation["llm_required_micro"],
                "protocol_metrics": evaluation["protocol_metrics"],
                "artifacts": {
                    name: str(path) for name, path in paths.items()
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
