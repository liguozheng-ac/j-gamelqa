"""Evaluate frozen held-out predictions only after prediction hashes are sealed."""

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from j_gamelqa.context_comparison import CONTEXT_SENSITIVE_ISSUES
from j_gamelqa.evaluate import calculate_subset_metrics, evaluate_detections
from j_gamelqa.heldout_freeze import PROTOCOL_SHA256, sha256_file
from j_gamelqa.hybrid import merge_hybrid_predictions
from j_gamelqa.io import load_reference_annotations, load_test_dataset
from j_gamelqa.llm_experiment import _bad_cases_with_raw
from j_gamelqa.models import Issue


PROJECT_ROOT = Path(__file__).resolve().parents[2]
METHOD_ORDER = (
    "Rule Only",
    "LLM Prompt v1",
    "LLM Prompt v2.1",
    "Hybrid Prompt v1",
    "Hybrid Prompt v2.1",
)
FOCUS_TYPES = (
    "mistranslation",
    "translationese",
    "keigo_mismatch",
    "first_person_mismatch",
    "character_voice_mismatch",
)


def _read_json(path: str | Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_predictions(path: str | Path) -> list[Issue]:
    return [Issue(**row) for row in _read_json(path)]


def _verify_prediction_freeze(output: Path) -> tuple[dict, dict]:
    preflight_path = output / "heldout_pre_evaluation_freeze.json"
    prediction_freeze_path = output / "heldout_prediction_freeze.json"
    preflight = _read_json(preflight_path)
    prediction_freeze = _read_json(prediction_freeze_path)
    if preflight["protocol_sha256"] != PROTOCOL_SHA256:
        raise RuntimeError("preflight protocol hash is not the registered protocol")
    if prediction_freeze["status"] != "all_predictions_frozen_before_evaluation":
        raise RuntimeError("predictions were not frozen before annotation access")
    paths = {
        "rule_predictions": output / "test_rule_predictions.json",
        "prompt_v1_config": output / "test_qwen35_prompt_v1_config.json",
        "prompt_v1_raw": output / "test_qwen35_prompt_v1_raw.jsonl",
        "prompt_v1_predictions": output / "test_qwen35_prompt_v1_predictions.json",
        "prompt_v21_config": output / "test_qwen35_prompt_v21_config.json",
        "prompt_v21_raw": output / "test_qwen35_prompt_v21_raw.jsonl",
        "prompt_v21_predictions": output / "test_qwen35_prompt_v21_predictions.json",
    }
    for name, expected_hash in prediction_freeze["artifact_sha256"].items():
        if sha256_file(paths[name]) != expected_hash:
            raise RuntimeError(f"frozen prediction artifact changed: {name}")
    for relative_path, expected_hash in preflight["source_sha256"].items():
        if sha256_file(PROJECT_ROOT / relative_path) != expected_hash:
            raise RuntimeError(f"frozen source changed after preflight: {relative_path}")
    return preflight, prediction_freeze


def _bad_cases(evaluation: dict) -> dict:
    return {
        "false_positives": evaluation["false_positives"],
        "false_negatives": evaluation["false_negatives"],
        "duplicate_predictions": evaluation["duplicate_predictions"],
        "unknown_prediction_types": evaluation["unknown_prediction_types"],
    }


def _with_context_metrics(evaluation: dict, references, predictions) -> dict:
    evaluation["context_sensitive_subset"] = calculate_subset_metrics(
        references, predictions, CONTEXT_SENSITIVE_ISSUES
    )
    return evaluation


def clean_false_alarm_metrics(test_frame, references, methods) -> dict:
    reference_ids = set(references["string_id"])
    clean_ids = sorted(set(test_frame["string_id"]) - reference_ids)
    return {
        "clean_sample_count": len(clean_ids),
        "clean_sample_ids": clean_ids,
        "methods": {
            name: {
                "false_alarmed_clean_samples": len(
                    set(clean_ids) & {item.string_id for item in predictions}
                ),
                "false_alarm_rate": (
                    len(set(clean_ids) & {item.string_id for item in predictions})
                    / len(clean_ids)
                    if clean_ids
                    else 0.0
                ),
                "false_alarm_ids": sorted(
                    set(clean_ids) & {item.string_id for item in predictions}
                ),
            }
            for name, predictions in methods.items()
        },
    }


def multi_issue_metrics(references, methods) -> dict:
    reference_types = defaultdict(set)
    for row in references.itertuples(index=False):
        reference_types[str(row.string_id)].add(str(row.issue_type))
    multi = {
        string_id: types
        for string_id, types in reference_types.items()
        if len(types) >= 2
    }
    method_results = {}
    for name, predictions in methods.items():
        predicted_types = defaultdict(set)
        for item in predictions:
            predicted_types[item.string_id].add(item.issue_type)
        fully = []
        partially = []
        missed = []
        for string_id, expected in sorted(multi.items()):
            detected = expected & predicted_types[string_id]
            if detected == expected:
                fully.append(string_id)
            elif detected:
                partially.append(string_id)
            else:
                missed.append(string_id)
        method_results[name] = {
            "fully_detected": len(fully),
            "partially_detected": len(partially),
            "completely_missed": len(missed),
            "fully_detected_ids": fully,
            "partially_detected_ids": partially,
            "completely_missed_ids": missed,
        }
    return {"multi_issue_sample_count": len(multi), "methods": method_results}


def _per_issue(evaluation: dict) -> dict[str, dict]:
    return {row["issue_type"]: row for row in evaluation["per_issue_type"]}


def _write_comparison_csv(path: Path, evaluations: dict) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=("method", "tp", "fp", "fn", "precision", "recall", "f1"),
        )
        writer.writeheader()
        for method in METHOD_ORDER:
            writer.writerow({"method": method, **evaluations[method]["overall_micro"]})


def run_heldout_evaluation(
    *,
    test_path: str | Path,
    annotations_path: str | Path,
    output_dir: str | Path,
) -> tuple[dict, dict[str, Path]]:
    output = Path(output_dir)
    paths = {
        "rule_evaluation": output / "test_rule_evaluation.json",
        "rule_bad_cases": output / "test_rule_bad_cases.json",
        "v1_evaluation": output / "test_qwen35_prompt_v1_evaluation.json",
        "v1_bad_cases": output / "test_qwen35_prompt_v1_bad_cases.json",
        "v21_evaluation": output / "test_qwen35_prompt_v21_evaluation.json",
        "v21_bad_cases": output / "test_qwen35_prompt_v21_bad_cases.json",
        "hybrid_v1_predictions": output / "test_hybrid_prompt_v1_predictions.json",
        "hybrid_v1_evaluation": output / "test_hybrid_prompt_v1_evaluation.json",
        "hybrid_v1_bad_cases": output / "test_hybrid_prompt_v1_bad_cases.json",
        "hybrid_v21_predictions": output / "test_hybrid_prompt_v21_predictions.json",
        "hybrid_v21_evaluation": output / "test_hybrid_prompt_v21_evaluation.json",
        "hybrid_v21_bad_cases": output / "test_hybrid_prompt_v21_bad_cases.json",
        "comparison_json": output / "heldout_method_comparison_v1.json",
        "comparison_csv": output / "heldout_method_comparison_v1.csv",
        "freeze_manifest": output / "heldout_evaluation_freeze_manifest.json",
    }
    existing = [str(path) for path in paths.values() if path.exists()]
    if existing:
        raise FileExistsError("held-out evaluation outputs already exist: " + ", ".join(existing))

    preflight, prediction_freeze = _verify_prediction_freeze(output)
    # Annotation access starts only after all frozen prediction/source checks above pass.
    test_frame = load_test_dataset(test_path)
    references = load_reference_annotations(annotations_path, test_frame)
    rule = _load_predictions(output / "test_rule_predictions.json")
    v1 = _load_predictions(output / "test_qwen35_prompt_v1_predictions.json")
    v21 = _load_predictions(output / "test_qwen35_prompt_v21_predictions.json")
    hybrid_v1_merge = merge_hybrid_predictions(rule, v1)
    hybrid_v21_merge = merge_hybrid_predictions(rule, v21)
    methods = {
        "Rule Only": rule,
        "LLM Prompt v1": v1,
        "LLM Prompt v2.1": v21,
        "Hybrid Prompt v1": hybrid_v1_merge.predictions,
        "Hybrid Prompt v2.1": hybrid_v21_merge.predictions,
    }
    evaluations = {
        name: _with_context_metrics(
            evaluate_detections(references, predictions, test_frame),
            references,
            predictions,
        )
        for name, predictions in methods.items()
    }
    evaluations["LLM Prompt v1"]["protocol_metrics"] = prediction_freeze["protocol"]["prompt_v1"]["protocol_metrics"]
    evaluations["LLM Prompt v2.1"]["protocol_metrics"] = prediction_freeze["protocol"]["prompt_v21"]["protocol_metrics"]
    evaluations["Hybrid Prompt v1"]["merge_diagnostics"] = {
        "policy": "all_rule_predictions__plus_llm_required_predictions",
        "excluded_llm_predictions": len(hybrid_v1_merge.llm_predictions_excluded_from_hybrid),
        "duplicate_predictions": hybrid_v1_merge.duplicate_predictions,
    }
    evaluations["Hybrid Prompt v2.1"]["merge_diagnostics"] = {
        "policy": "all_rule_predictions__plus_llm_required_predictions",
        "excluded_llm_predictions": len(hybrid_v21_merge.llm_predictions_excluded_from_hybrid),
        "duplicate_predictions": hybrid_v21_merge.duplicate_predictions,
    }

    _write_json(paths["rule_evaluation"], evaluations["Rule Only"])
    _write_json(paths["rule_bad_cases"], _bad_cases(evaluations["Rule Only"]))
    _write_json(paths["v1_evaluation"], evaluations["LLM Prompt v1"])
    v1_raw = [json.loads(line) for line in (output / "test_qwen35_prompt_v1_raw.jsonl").read_text(encoding="utf-8").splitlines() if line]
    _write_json(paths["v1_bad_cases"], _bad_cases_with_raw(evaluations["LLM Prompt v1"], v1_raw))
    _write_json(paths["v21_evaluation"], evaluations["LLM Prompt v2.1"])
    v21_raw = [json.loads(line) for line in (output / "test_qwen35_prompt_v21_raw.jsonl").read_text(encoding="utf-8").splitlines() if line]
    _write_json(paths["v21_bad_cases"], _bad_cases_with_raw(evaluations["LLM Prompt v2.1"], v21_raw))
    _write_json(paths["hybrid_v1_predictions"], [item.to_dict() for item in hybrid_v1_merge.predictions])
    _write_json(paths["hybrid_v1_evaluation"], evaluations["Hybrid Prompt v1"])
    _write_json(paths["hybrid_v1_bad_cases"], _bad_cases(evaluations["Hybrid Prompt v1"]))
    _write_json(paths["hybrid_v21_predictions"], [item.to_dict() for item in hybrid_v21_merge.predictions])
    _write_json(paths["hybrid_v21_evaluation"], evaluations["Hybrid Prompt v2.1"])
    _write_json(paths["hybrid_v21_bad_cases"], _bad_cases(evaluations["Hybrid Prompt v2.1"]))

    dev_paths = {
        "Rule Only": output / "dev_evaluation.json",
        "LLM Prompt v1": output / "qwen35_9b_with_context_evaluation.json",
        "LLM Prompt v2.1": output / "qwen35_9b_with_context_prompt_v21_dev_evaluation.json",
        "Hybrid Prompt v1": output / "hybrid_rule_qwen35_context_evaluation.json",
        "Hybrid Prompt v2.1": output / "hybrid_rule_qwen35_context_prompt_v21_dev_evaluation.json",
    }
    dev_evaluations = {name: _read_json(path) for name, path in dev_paths.items()}
    comparison = {
        "protocol_version": "heldout_evaluation_protocol_v1",
        "primary_metric": "overall_detection_f1",
        "methods": {
            name: {
                "overall": evaluations[name]["overall_micro"],
                "rule_addressable": evaluations[name]["rule_addressable_micro"],
                "llm_required": evaluations[name]["llm_required_micro"],
                "context_sensitive": evaluations[name]["context_sensitive_subset"],
            }
            for name in METHOD_ORDER
        },
        "focus_per_issue": {
            issue_type: {
                name: _per_issue(evaluations[name])[issue_type]
                for name in METHOD_ORDER
            }
            for issue_type in FOCUS_TYPES
        },
        "development_to_heldout_gap": {
            name: {
                "development_f1": dev_evaluations[name]["overall_micro"]["f1"],
                "heldout_f1": evaluations[name]["overall_micro"]["f1"],
                "test_minus_dev": evaluations[name]["overall_micro"]["f1"]
                - dev_evaluations[name]["overall_micro"]["f1"],
            }
            for name in METHOD_ORDER
        },
        "clean_false_alarm": clean_false_alarm_metrics(test_frame, references, methods),
        "multi_issue": multi_issue_metrics(references, methods),
        "protocol_comparison": {
            "Prompt v1": prediction_freeze["protocol"]["prompt_v1"]["protocol_metrics"],
            "Prompt v2.1": prediction_freeze["protocol"]["prompt_v21"]["protocol_metrics"],
        },
        "winner_policy": {
            "primary": "Hybrid Overall F1",
            "broadly_comparable_threshold": 0.02,
            "secondary": [
                "LLM-required F1",
                "Precision/Recall trade-off",
                "Protocol reliability",
                "Paired bad-case pattern",
            ],
        },
    }
    _write_json(paths["comparison_json"], comparison)
    _write_comparison_csv(paths["comparison_csv"], evaluations)

    result_files = [
        output / "test_rule_predictions.json",
        output / "test_qwen35_prompt_v1_config.json",
        output / "test_qwen35_prompt_v1_raw.jsonl",
        output / "test_qwen35_prompt_v1_predictions.json",
        output / "test_qwen35_prompt_v21_config.json",
        output / "test_qwen35_prompt_v21_raw.jsonl",
        output / "test_qwen35_prompt_v21_predictions.json",
        output / "heldout_prediction_freeze.json",
        *[path for name, path in paths.items() if name != "freeze_manifest"],
    ]
    manifest = {
        "freeze_id": "heldout_evaluation_v1",
        "frozen_at_utc": datetime.now(UTC).isoformat(),
        "status": "first_and_final_heldout_result_frozen",
        "test_sha256": {
            "test.csv": sha256_file(test_path),
            "test_annotations.csv": sha256_file(annotations_path),
        },
        "prompt_hashes": preflight["hashes"],
        "protocol_sha256": preflight["protocol_sha256"],
        "source_sha256": preflight["source_sha256"],
        "result_artifact_sha256": {
            path.name: sha256_file(path) for path in result_files
        },
        "no_retuning_policy": "future development requires Test v2 or external human-reviewed evaluation",
    }
    _write_json(paths["freeze_manifest"], manifest)
    return comparison, paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate frozen held-out predictions.")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "outputs")
    args = parser.parse_args()
    comparison, paths = run_heldout_evaluation(
        test_path=PROJECT_ROOT / "data" / "test.csv",
        annotations_path=PROJECT_ROOT / "data" / "test_annotations.csv",
        output_dir=args.output_dir,
    )
    print(
        json.dumps(
            {
                "methods": {
                    name: comparison["methods"][name]["overall"]
                    for name in METHOD_ORDER
                },
                "artifacts": {name: str(path) for name, path in paths.items()},
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
