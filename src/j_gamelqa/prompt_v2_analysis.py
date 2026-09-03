"""Artifact-only Prompt v1/v2 and Hybrid Development comparison."""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from j_gamelqa.context_comparison import (
    CONTEXT_SENSITIVE_ISSUES,
    calculate_metric_delta,
)
from j_gamelqa.evaluate import calculate_subset_metrics, evaluate_detections
from j_gamelqa.hybrid import merge_hybrid_predictions
from j_gamelqa.hybrid_experiment import build_paired_analysis
from j_gamelqa.io import load_dev_dataset, load_reference_annotations
from j_gamelqa.models import Issue
from j_gamelqa.taxonomy import REGISTERED_ISSUE_TYPES


PROJECT_ROOT = Path(__file__).resolve().parents[2]
HYBRID_EXPERIMENT_ID = "rule_qwen35_context_prompt_v2_dev_hybrid_v1"


def _read_json(path: str | Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _load_predictions(path: str | Path) -> list[Issue]:
    return [Issue(**record) for record in _read_json(path)]


def _sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest().upper()


def _keys(predictions: list[Issue]) -> set[tuple[str, str]]:
    return {(item.string_id, item.issue_type) for item in predictions}


def _reference_keys(reference_annotations) -> set[tuple[str, str]]:
    return {
        (str(row.string_id), str(row.issue_type))
        for row in reference_annotations.itertuples(index=False)
    }


def paired_prompt_changes(
    reference_annotations,
    v1_predictions: list[Issue],
    v2_predictions: list[Issue],
) -> dict[str, list[dict]]:
    references = _reference_keys(reference_annotations)
    v1_keys = _keys(v1_predictions)
    v2_keys = _keys(v2_predictions)
    v1_false_positives = v1_keys - references
    v2_false_positives = v2_keys - references

    def records(keys, before, after):
        return [
            {
                "string_id": key[0],
                "issue_type": key[1],
                "v1_status": before,
                "v2_status": after,
            }
            for key in sorted(keys)
        ]

    by_id_v1 = {}
    by_id_v2 = {}
    for string_id, issue_type in v1_keys:
        by_id_v1.setdefault(string_id, set()).add(issue_type)
    for string_id, issue_type in v2_keys:
        by_id_v2.setdefault(string_id, set()).add(issue_type)
    type_changes = []
    for string_id in sorted(set(by_id_v1) | set(by_id_v2)):
        removed = sorted(by_id_v1.get(string_id, set()) - by_id_v2.get(string_id, set()))
        added = sorted(by_id_v2.get(string_id, set()) - by_id_v1.get(string_id, set()))
        if removed and added:
            type_changes.append(
                {
                    "string_id": string_id,
                    "removed_types": removed,
                    "added_types": added,
                }
            )

    return {
        "resolved_false_positives": records(
            v1_false_positives - v2_false_positives,
            "false_positive",
            "not_predicted",
        ),
        "new_false_positives": records(
            v2_false_positives - v1_false_positives,
            "not_predicted",
            "false_positive",
        ),
        "false_negative_to_true_positive": records(
            (references & v2_keys) - v1_keys,
            "false_negative",
            "true_positive",
        ),
        "true_positive_to_false_negative": records(
            (references & v1_keys) - v2_keys,
            "true_positive",
            "false_negative",
        ),
        "type_changes": type_changes,
    }


def build_prompt_comparison(
    reference_annotations,
    v1_predictions: list[Issue],
    v2_predictions: list[Issue],
    v1_evaluation: dict,
    v2_evaluation: dict,
) -> dict:
    v1_context = calculate_subset_metrics(
        reference_annotations, v1_predictions, CONTEXT_SENSITIVE_ISSUES
    )
    v2_context = calculate_subset_metrics(
        reference_annotations, v2_predictions, CONTEXT_SENSITIVE_ISSUES
    )
    v1_per_issue = {
        row["issue_type"]: row for row in v1_evaluation["per_issue_type"]
    }
    v2_per_issue = {
        row["issue_type"]: row for row in v2_evaluation["per_issue_type"]
    }
    return {
        "experiments": {
            "prompt_v1": v1_evaluation.get("experiment_id"),
            "prompt_v2": v2_evaluation.get("experiment_id"),
            "dataset": "frozen 48-item Development Set",
        },
        "overall": {
            "prompt_v1": v1_evaluation["overall_micro"],
            "prompt_v2": v2_evaluation["overall_micro"],
            "delta": calculate_metric_delta(
                v1_evaluation["overall_micro"], v2_evaluation["overall_micro"]
            ),
        },
        "llm_required": {
            "prompt_v1": v1_evaluation["llm_required_micro"],
            "prompt_v2": v2_evaluation["llm_required_micro"],
            "delta": calculate_metric_delta(
                v1_evaluation["llm_required_micro"],
                v2_evaluation["llm_required_micro"],
            ),
        },
        "context_sensitive": {
            "issue_types": sorted(CONTEXT_SENSITIVE_ISSUES),
            "prompt_v1": v1_context,
            "prompt_v2": v2_context,
            "delta": calculate_metric_delta(v1_context, v2_context),
        },
        "per_issue": [
            {
                "issue_type": issue_type,
                "prompt_v1": v1_per_issue[issue_type],
                "prompt_v2": v2_per_issue[issue_type],
                "delta": {
                    "prediction_count": (
                        v2_per_issue[issue_type]["prediction_count"]
                        - v1_per_issue[issue_type]["prediction_count"]
                    ),
                    **calculate_metric_delta(
                        v1_per_issue[issue_type], v2_per_issue[issue_type]
                    ),
                },
            }
            for issue_type in sorted(REGISTERED_ISSUE_TYPES)
        ],
        "paired_changes": paired_prompt_changes(
            reference_annotations, v1_predictions, v2_predictions
        ),
    }


def analysis_artifact_paths(output_dir: str | Path) -> dict[str, Path]:
    destination = Path(output_dir)
    return {
        "prompt_comparison": destination / "prompt_v1_vs_v2_dev_comparison.json",
        "hybrid_config": destination / "hybrid_rule_qwen35_context_prompt_v2_dev_config.json",
        "hybrid_predictions": destination / "hybrid_rule_qwen35_context_prompt_v2_dev_predictions.json",
        "hybrid_evaluation": destination / "hybrid_rule_qwen35_context_prompt_v2_dev_evaluation.json",
        "hybrid_bad_cases": destination / "hybrid_rule_qwen35_context_prompt_v2_dev_bad_cases.json",
        "hybrid_comparison": destination / "hybrid_v1_vs_prompt_v2_dev_comparison.json",
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
    v2_config_path: str | Path,
    output_dir: str | Path,
) -> tuple[dict, dict, dict, dict[str, Path]]:
    """Compare sealed DEV artifacts and build Hybrid Prompt v2 without a provider."""
    paths = analysis_artifact_paths(output_dir)
    existing = [path for path in paths.values() if path.exists()]
    if existing:
        raise FileExistsError(
            "Prompt v2 analysis artifacts already exist and will not be overwritten: "
            + ", ".join(str(path) for path in existing)
        )

    dev_frame = load_dev_dataset(dev_path)
    if set(dev_frame["string_id"]) != {
        f"DEV_{number:03d}" for number in range(1, 49)
    }:
        raise ValueError("Prompt comparison accepts only the frozen Development Set")
    references = load_reference_annotations(annotations_path, dev_frame)
    rules = _load_predictions(rule_predictions_path)
    v1_predictions = _load_predictions(v1_predictions_path)
    v2_predictions = _load_predictions(v2_predictions_path)
    v1_evaluation = _read_json(v1_evaluation_path)
    v2_evaluation = _read_json(v2_evaluation_path)
    v1_hybrid_evaluation = _read_json(v1_hybrid_evaluation_path)

    prompt_comparison = build_prompt_comparison(
        references,
        v1_predictions,
        v2_predictions,
        v1_evaluation,
        v2_evaluation,
    )
    merge_result = merge_hybrid_predictions(rules, v2_predictions)
    hybrid_evaluation = evaluate_detections(
        references, merge_result.predictions, dev_frame
    )
    hybrid_evaluation["experiment_id"] = HYBRID_EXPERIMENT_ID
    hybrid_evaluation["context_sensitive_subset"] = calculate_subset_metrics(
        references, merge_result.predictions, CONTEXT_SENSITIVE_ISSUES
    )
    hybrid_evaluation["merge_diagnostics"] = {
        "rule_predictions": len(rules),
        "llm_predictions_received": len(v2_predictions),
        "llm_predictions_included": (
            len(v2_predictions)
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
        references, rules, v2_predictions, merge_result
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

    hybrid_comparison = {
        "hybrid_v1": v1_hybrid_evaluation["overall_micro"],
        "hybrid_prompt_v2": hybrid_evaluation["overall_micro"],
        "overall_delta": calculate_metric_delta(
            v1_hybrid_evaluation["overall_micro"],
            hybrid_evaluation["overall_micro"],
        ),
        "rule_addressable": {
            "hybrid_v1": v1_hybrid_evaluation["rule_addressable_micro"],
            "hybrid_prompt_v2": hybrid_evaluation["rule_addressable_micro"],
            "delta": calculate_metric_delta(
                v1_hybrid_evaluation["rule_addressable_micro"],
                hybrid_evaluation["rule_addressable_micro"],
            ),
        },
        "llm_required": {
            "hybrid_v1": v1_hybrid_evaluation["llm_required_micro"],
            "hybrid_prompt_v2": hybrid_evaluation["llm_required_micro"],
            "delta": calculate_metric_delta(
                v1_hybrid_evaluation["llm_required_micro"],
                hybrid_evaluation["llm_required_micro"],
            ),
        },
        "context_sensitive": {
            "hybrid_v1": v1_hybrid_evaluation["context_sensitive_subset"],
            "hybrid_prompt_v2": hybrid_evaluation["context_sensitive_subset"],
            "delta": calculate_metric_delta(
                v1_hybrid_evaluation["context_sensitive_subset"],
                hybrid_evaluation["context_sensitive_subset"],
            ),
        },
    }

    v2_config = _read_json(v2_config_path)
    hybrid_config = {
        "experiment_id": HYBRID_EXPERIMENT_ID,
        "created_at_utc": datetime.now(UTC).isoformat(),
        "dataset": "frozen 48-item Development Set",
        "rule_component": "frozen rule_baseline_v1",
        "llm_component": v2_config["experiment_id"],
        "llm_prompt_version": v2_config["prompt_version"],
        "llm_input_mode": v2_config["input_mode"],
        "hybrid_policy": "all_rule_predictions__plus_llm_required_predictions",
        "provider_calls": 0,
        "component_sha256": {
            "rule_predictions": _sha256(rule_predictions_path),
            "v2_predictions": _sha256(v2_predictions_path),
        },
    }

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    _write_json(paths["prompt_comparison"], prompt_comparison)
    _write_json(paths["hybrid_config"], hybrid_config)
    _write_json(
        paths["hybrid_predictions"],
        [item.to_dict() for item in merge_result.predictions],
    )
    _write_json(paths["hybrid_evaluation"], hybrid_evaluation)
    _write_json(paths["hybrid_bad_cases"], hybrid_bad_cases)
    _write_json(paths["hybrid_comparison"], hybrid_comparison)
    return prompt_comparison, hybrid_evaluation, hybrid_comparison, paths


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build Prompt v1/v2 and Hybrid comparisons from DEV artifacts."
    )
    parser.add_argument(
        "--output-dir", type=Path, default=PROJECT_ROOT / "outputs"
    )
    args = parser.parse_args()
    output = args.output_dir
    prompt_comparison, hybrid_evaluation, hybrid_comparison, paths = (
        run_artifact_analysis(
            dev_path=PROJECT_ROOT / "data" / "dev.csv",
            annotations_path=PROJECT_ROOT / "data" / "dev_annotations.csv",
            rule_predictions_path=output / "dev_rule_predictions.json",
            v1_predictions_path=output / "qwen35_9b_with_context_predictions.json",
            v1_evaluation_path=output / "qwen35_9b_with_context_evaluation.json",
            v1_hybrid_evaluation_path=output / "hybrid_rule_qwen35_context_evaluation.json",
            v2_predictions_path=output / "qwen35_9b_with_context_prompt_v2_dev_predictions.json",
            v2_evaluation_path=output / "qwen35_9b_with_context_prompt_v2_dev_evaluation.json",
            v2_config_path=output / "qwen35_9b_with_context_prompt_v2_dev_config.json",
            output_dir=output,
        )
    )
    print(
        json.dumps(
            {
                "provider_calls": 0,
                "prompt_v2_llm_required": prompt_comparison["llm_required"][
                    "prompt_v2"
                ],
                "hybrid_prompt_v2": hybrid_evaluation["overall_micro"],
                "hybrid_delta": hybrid_comparison["overall_delta"],
                "artifacts": {name: str(path) for name, path in paths.items()},
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
