"""Artifact-only v1/v2/v2.1 comparison, Hybrid, and candidate gate."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from j_gamelqa.candidate_selection import evaluate_candidate_gate
from j_gamelqa.context_comparison import CONTEXT_SENSITIVE_ISSUES
from j_gamelqa.evaluate import calculate_subset_metrics, evaluate_detections
from j_gamelqa.hybrid import merge_hybrid_predictions
from j_gamelqa.hybrid_experiment import build_paired_analysis
from j_gamelqa.io import load_dev_dataset, load_reference_annotations
from j_gamelqa.prompt_v2_analysis import (
    _load_predictions,
    _read_json,
    _sha256,
    _write_json,
    paired_prompt_changes,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
HYBRID_EXPERIMENT_ID = "rule_qwen35_context_prompt_v21_dev_hybrid_v1"
FOCUS_ISSUE_TYPES = (
    "mistranslation",
    "translationese",
    "keigo_mismatch",
    "first_person_mismatch",
    "character_voice_mismatch",
)


def analysis_artifact_paths(output_dir: str | Path) -> dict[str, Path]:
    destination = Path(output_dir)
    return {
        "comparison": destination / "prompt_v1_v2_v21_dev_comparison.json",
        "hybrid_config": destination
        / "hybrid_rule_qwen35_context_prompt_v21_dev_config.json",
        "hybrid_predictions": destination
        / "hybrid_rule_qwen35_context_prompt_v21_dev_predictions.json",
        "hybrid_evaluation": destination
        / "hybrid_rule_qwen35_context_prompt_v21_dev_evaluation.json",
        "hybrid_bad_cases": destination
        / "hybrid_rule_qwen35_context_prompt_v21_dev_bad_cases.json",
        "candidate_gate": destination / "prompt_v21_dev_candidate_gate.json",
    }


def _per_issue_map(evaluation: dict) -> dict[str, dict]:
    return {row["issue_type"]: row for row in evaluation["per_issue_type"]}


def _scope_metrics(references, predictions, evaluation: dict) -> dict:
    return {
        "overall": evaluation["overall_micro"],
        "llm_required": evaluation["llm_required_micro"],
        "context_sensitive": calculate_subset_metrics(
            references, predictions, CONTEXT_SENSITIVE_ISSUES
        ),
    }


def run_artifact_analysis(
    *,
    dev_path: str | Path,
    annotations_path: str | Path,
    rule_predictions_path: str | Path,
    v1_predictions_path: str | Path,
    v1_evaluation_path: str | Path,
    v1_hybrid_evaluation_path: str | Path,
    v2_predictions_path: str | Path,
    v2_evaluation_path: str | Path,
    v2_hybrid_evaluation_path: str | Path,
    v21_predictions_path: str | Path,
    v21_evaluation_path: str | Path,
    v21_config_path: str | Path,
    output_dir: str | Path,
) -> tuple[dict, dict, dict, dict[str, Path]]:
    """Analyze frozen DEV artifacts without making provider calls."""
    paths = analysis_artifact_paths(output_dir)
    existing = [path for path in paths.values() if path.exists()]
    if existing:
        raise FileExistsError(
            "Prompt v2.1 analysis artifacts already exist and will not be overwritten: "
            + ", ".join(str(path) for path in existing)
        )

    dev_frame = load_dev_dataset(dev_path)
    expected_ids = {f"DEV_{number:03d}" for number in range(1, 49)}
    if len(dev_frame) != 48 or set(dev_frame["string_id"]) != expected_ids:
        raise ValueError("Prompt v2.1 analysis accepts only frozen Development")
    references = load_reference_annotations(annotations_path, dev_frame)

    rules = _load_predictions(rule_predictions_path)
    predictions = {
        "v1": _load_predictions(v1_predictions_path),
        "v2": _load_predictions(v2_predictions_path),
        "v2.1": _load_predictions(v21_predictions_path),
    }
    evaluations = {
        "v1": _read_json(v1_evaluation_path),
        "v2": _read_json(v2_evaluation_path),
        "v2.1": _read_json(v21_evaluation_path),
    }
    scopes = {
        version: _scope_metrics(references, predictions[version], evaluations[version])
        for version in predictions
    }
    per_issue = {version: _per_issue_map(evaluations[version]) for version in predictions}
    comparison = {
        "dataset": "frozen 48-item Development Set",
        "versions": {
            version: evaluations[version].get("experiment_id") for version in predictions
        },
        "scopes": {
            scope: {version: scopes[version][scope] for version in predictions}
            for scope in ("overall", "llm_required", "context_sensitive")
        },
        "focus_per_issue": {
            issue_type: {
                version: per_issue[version][issue_type] for version in predictions
            }
            for issue_type in FOCUS_ISSUE_TYPES
        },
        "pairwise": {
            "v1_to_v2.1": paired_prompt_changes(
                references, predictions["v1"], predictions["v2.1"]
            ),
            "v2_to_v2.1": paired_prompt_changes(
                references, predictions["v2"], predictions["v2.1"]
            ),
        },
    }

    merge_result = merge_hybrid_predictions(rules, predictions["v2.1"])
    hybrid_evaluation = evaluate_detections(
        references, merge_result.predictions, dev_frame
    )
    hybrid_evaluation["experiment_id"] = HYBRID_EXPERIMENT_ID
    hybrid_evaluation["context_sensitive_subset"] = calculate_subset_metrics(
        references, merge_result.predictions, CONTEXT_SENSITIVE_ISSUES
    )
    hybrid_evaluation["merge_diagnostics"] = {
        "rule_predictions": len(rules),
        "llm_predictions_received": len(predictions["v2.1"]),
        "llm_predictions_included": (
            len(predictions["v2.1"])
            - len(merge_result.llm_predictions_excluded_from_hybrid)
        ),
        "llm_predictions_excluded": len(
            merge_result.llm_predictions_excluded_from_hybrid
        ),
        "excluded_predictions": [
            item.to_dict()
            for item in merge_result.llm_predictions_excluded_from_hybrid
        ],
        "duplicate_predictions": merge_result.duplicate_predictions,
    }
    paired_hybrid = build_paired_analysis(
        references, rules, predictions["v2.1"], merge_result
    )
    fp_sources = {
        (item["string_id"], item["issue_type"]): item["source_component"]
        for item in paired_hybrid["hybrid_false_positives"]
    }
    attributed_fps = []
    for item in hybrid_evaluation["false_positives"]:
        record = dict(item)
        record["source_component"] = fp_sources[
            (record["string_id"], record["issue_type"])
        ]
        attributed_fps.append(record)
    hybrid_bad_cases = {
        "false_positives": attributed_fps,
        "false_negatives": hybrid_evaluation["false_negatives"],
        "paired_analysis": paired_hybrid,
        "duplicate_predictions": hybrid_evaluation["duplicate_predictions"],
        "unknown_prediction_types": hybrid_evaluation["unknown_prediction_types"],
    }

    candidate_gate = evaluate_candidate_gate(
        evaluations["v2.1"]["llm_required_micro"],
        hybrid_evaluation["overall_micro"],
        evaluations["v2.1"]["protocol_metrics"],
    )
    candidate_gate["evaluated_experiment"] = evaluations["v2.1"].get(
        "experiment_id"
    )
    candidate_gate["actual"] = {
        "llm_required": evaluations["v2.1"]["llm_required_micro"],
        "hybrid_overall": hybrid_evaluation["overall_micro"],
        "protocol": evaluations["v2.1"]["protocol_metrics"],
    }

    v21_config = _read_json(v21_config_path)
    hybrid_config = {
        "experiment_id": HYBRID_EXPERIMENT_ID,
        "created_at_utc": datetime.now(UTC).isoformat(),
        "dataset": "frozen 48-item Development Set",
        "rule_component": "frozen rule_baseline_v1",
        "llm_component": v21_config["experiment_id"],
        "llm_prompt_version": v21_config["prompt_version"],
        "llm_input_mode": v21_config["input_mode"],
        "hybrid_policy": "all_rule_predictions__plus_llm_required_predictions",
        "provider_calls": 0,
        "component_sha256": {
            "rule_predictions": _sha256(rule_predictions_path),
            "v2.1_predictions": _sha256(v21_predictions_path),
        },
        "frozen_comparison_inputs": {
            "v1_hybrid_evaluation_sha256": _sha256(v1_hybrid_evaluation_path),
            "v2_hybrid_evaluation_sha256": _sha256(v2_hybrid_evaluation_path),
        },
    }

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    _write_json(paths["comparison"], comparison)
    _write_json(paths["hybrid_config"], hybrid_config)
    _write_json(
        paths["hybrid_predictions"],
        [item.to_dict() for item in merge_result.predictions],
    )
    _write_json(paths["hybrid_evaluation"], hybrid_evaluation)
    _write_json(paths["hybrid_bad_cases"], hybrid_bad_cases)
    _write_json(paths["candidate_gate"], candidate_gate)
    return comparison, hybrid_evaluation, candidate_gate, paths


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze Prompt v2.1 and apply the pre-registered candidate gate."
    )
    parser.add_argument(
        "--output-dir", type=Path, default=PROJECT_ROOT / "outputs"
    )
    args = parser.parse_args()
    output = args.output_dir
    comparison, hybrid_evaluation, candidate_gate, paths = run_artifact_analysis(
        dev_path=PROJECT_ROOT / "data" / "dev.csv",
        annotations_path=PROJECT_ROOT / "data" / "dev_annotations.csv",
        rule_predictions_path=output / "dev_rule_predictions.json",
        v1_predictions_path=output / "qwen35_9b_with_context_predictions.json",
        v1_evaluation_path=output / "qwen35_9b_with_context_evaluation.json",
        v1_hybrid_evaluation_path=output
        / "hybrid_rule_qwen35_context_evaluation.json",
        v2_predictions_path=output
        / "qwen35_9b_with_context_prompt_v2_dev_predictions.json",
        v2_evaluation_path=output
        / "qwen35_9b_with_context_prompt_v2_dev_evaluation.json",
        v2_hybrid_evaluation_path=output
        / "hybrid_rule_qwen35_context_prompt_v2_dev_evaluation.json",
        v21_predictions_path=output
        / "qwen35_9b_with_context_prompt_v21_dev_predictions.json",
        v21_evaluation_path=output
        / "qwen35_9b_with_context_prompt_v21_dev_evaluation.json",
        v21_config_path=output
        / "qwen35_9b_with_context_prompt_v21_dev_config.json",
        output_dir=output,
    )
    print(
        json.dumps(
            {
                "provider_calls": 0,
                "v2.1_llm_required": comparison["scopes"]["llm_required"][
                    "v2.1"
                ],
                "hybrid_v2.1": hybrid_evaluation["overall_micro"],
                "candidate_decision": candidate_gate["decision"],
                "artifacts": {name: str(path) for name, path in paths.items()},
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
