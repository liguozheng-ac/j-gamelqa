"""Artifact-only Rule + context-aware LLM Hybrid v1 experiment."""

import argparse
import csv
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from j_gamelqa.context_comparison import (
    CONTEXT_SENSITIVE_ISSUES,
    calculate_metric_delta,
)
from j_gamelqa.evaluate import calculate_subset_metrics, evaluate_detections
from j_gamelqa.hybrid import HybridMergeResult, merge_hybrid_predictions
from j_gamelqa.io import load_dev_dataset, load_reference_annotations
from j_gamelqa.models import Issue
from j_gamelqa.taxonomy import (
    LLM_REQUIRED_ISSUE_TYPES,
    REGISTERED_ISSUE_TYPES,
    RULE_ADDRESSABLE_ISSUE_TYPES,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_ID = "rule_qwen35_context_hybrid_v1"
METHOD_NAMES = (
    "rule_only",
    "llm_no_context",
    "llm_with_context",
    "hybrid",
)
SCOPE_NAMES = (
    "overall",
    "rule_addressable",
    "llm_required",
    "context_sensitive",
)


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
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _detection_keys(predictions: list[Issue]) -> set[tuple[str, str]]:
    return {
        (prediction.string_id, prediction.issue_type)
        for prediction in predictions
    }


def _reference_keys(reference_annotations: pd.DataFrame) -> set[tuple[str, str]]:
    return {
        (str(row.string_id), str(row.issue_type))
        for row in reference_annotations.itertuples(index=False)
    }


def _metric_scopes(
    evaluation: dict,
    context_sensitive: dict,
) -> dict[str, dict]:
    return {
        "overall": evaluation["overall_micro"],
        "rule_addressable": evaluation["rule_addressable_micro"],
        "llm_required": evaluation["llm_required_micro"],
        "context_sensitive": context_sensitive,
    }


def _attributed_record(
    string_id: str,
    issue_type: str,
    rule_keys: set[tuple[str, str]],
    llm_keys: set[tuple[str, str]],
) -> dict[str, str]:
    key = (string_id, issue_type)
    sources = []
    if key in rule_keys:
        sources.append("rule")
    if key in llm_keys:
        sources.append("llm")
    return {
        "string_id": string_id,
        "issue_type": issue_type,
        "source_component": "+".join(sources),
    }


def build_paired_analysis(
    reference_annotations: pd.DataFrame,
    rule_predictions: list[Issue],
    llm_with_context_predictions: list[Issue],
    merge_result: HybridMergeResult,
) -> dict[str, list[dict[str, str]]]:
    """Explain which component supplies fixes, FPs, and remaining FNs."""
    references = _reference_keys(reference_annotations)
    rule_keys = _detection_keys(rule_predictions)
    llm_all_keys = _detection_keys(llm_with_context_predictions)
    llm_included_keys = {
        key for key in llm_all_keys if key[1] in LLM_REQUIRED_ISSUE_TYPES
    }
    hybrid_keys = _detection_keys(merge_result.predictions)

    fixed_by_rule = sorted((references & hybrid_keys) - llm_all_keys)
    fixed_by_llm = sorted((references & hybrid_keys) - rule_keys)
    false_positives = sorted(hybrid_keys - references)
    false_negatives = sorted(references - hybrid_keys)

    return {
        "fixed_by_rule": [
            {
                "string_id": key[0],
                "issue_type": key[1],
                "llm_status": "false_negative",
                "hybrid_status": "true_positive",
                "source_component": "rule",
            }
            for key in fixed_by_rule
        ],
        "fixed_by_llm": [
            {
                "string_id": key[0],
                "issue_type": key[1],
                "rule_status": "false_negative",
                "hybrid_status": "true_positive",
                "source_component": "llm",
            }
            for key in fixed_by_llm
        ],
        "hybrid_false_positives": [
            _attributed_record(key[0], key[1], rule_keys, llm_included_keys)
            for key in false_positives
        ],
        "remaining_false_negatives": [
            {"string_id": key[0], "issue_type": key[1]}
            for key in false_negatives
        ],
    }


def build_method_comparison(
    reference_annotations: pd.DataFrame,
    dev_frame: pd.DataFrame,
    predictions_by_method: dict[str, list[Issue]],
) -> tuple[dict, dict[str, dict]]:
    """Evaluate all four methods with one shared harness and schema."""
    evaluations = {}
    scopes = {}
    for method in METHOD_NAMES:
        predictions = predictions_by_method[method]
        evaluation = evaluate_detections(
            reference_annotations,
            predictions,
            dev_frame,
        )
        context_sensitive = calculate_subset_metrics(
            reference_annotations,
            predictions,
            CONTEXT_SENSITIVE_ISSUES,
        )
        evaluations[method] = evaluation
        scopes[method] = _metric_scopes(evaluation, context_sensitive)

    per_issue_maps = {
        method: {
            row["issue_type"]: row
            for row in evaluations[method]["per_issue_type"]
        }
        for method in METHOD_NAMES
    }
    per_issue = [
        {
            "issue_type": issue_type,
            **{
                method: per_issue_maps[method][issue_type]
                for method in METHOD_NAMES
            },
        }
        for issue_type in sorted(REGISTERED_ISSUE_TYPES)
    ]

    def pairwise(before: str, after: str) -> dict[str, dict]:
        return {
            scope: calculate_metric_delta(
                scopes[before][scope], scopes[after][scope]
            )
            for scope in SCOPE_NAMES
        }

    comparison = {
        "methods": {
            method: {
                "overall": scopes[method]["overall"],
                "rule_addressable": scopes[method]["rule_addressable"],
                "llm_required": scopes[method]["llm_required"],
                "context_sensitive": scopes[method]["context_sensitive"],
            }
            for method in METHOD_NAMES
        },
        "overall": {
            method: scopes[method]["overall"] for method in METHOD_NAMES
        },
        "rule_addressable": {
            method: scopes[method]["rule_addressable"]
            for method in METHOD_NAMES
        },
        "llm_required": {
            method: scopes[method]["llm_required"] for method in METHOD_NAMES
        },
        "context_sensitive": {
            method: scopes[method]["context_sensitive"]
            for method in METHOD_NAMES
        },
        "per_issue": per_issue,
        "pairwise": {
            "hybrid_vs_rule": pairwise("rule_only", "hybrid"),
            "hybrid_vs_llm_with_context": pairwise(
                "llm_with_context", "hybrid"
            ),
        },
    }
    return comparison, evaluations


def _comparison_csv_rows(comparison: dict) -> list[dict]:
    rows = []
    for scope in SCOPE_NAMES:
        for method in METHOD_NAMES:
            rows.append(
                {
                    "scope": scope,
                    "method": method,
                    **comparison[scope][method],
                }
            )
    return rows


def _write_comparison_csv(path: Path, comparison: dict) -> None:
    rows = _comparison_csv_rows(comparison)
    fieldnames = (
        "scope",
        "method",
        "tp",
        "fp",
        "fn",
        "precision",
        "recall",
        "f1",
    )
    with path.open("w", encoding="utf-8-sig", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def artifact_paths(output_dir: str | Path) -> dict[str, Path]:
    destination = Path(output_dir)
    return {
        "config": destination / "hybrid_rule_qwen35_context_config.json",
        "predictions": (
            destination / "hybrid_rule_qwen35_context_predictions.json"
        ),
        "evaluation": (
            destination / "hybrid_rule_qwen35_context_evaluation.json"
        ),
        "bad_cases": (
            destination / "hybrid_rule_qwen35_context_bad_cases.json"
        ),
        "comparison": destination / "method_comparison_v1.json",
        "comparison_csv": destination / "method_comparison_v1.csv",
    }


def run_artifact_experiment(
    *,
    dev_path: str | Path,
    annotations_path: str | Path,
    rule_predictions_path: str | Path,
    rule_evaluation_path: str | Path,
    llm_no_context_predictions_path: str | Path,
    llm_no_context_evaluation_path: str | Path,
    llm_with_context_predictions_path: str | Path,
    llm_with_context_evaluation_path: str | Path,
    llm_with_context_config_path: str | Path,
    output_dir: str | Path,
) -> tuple[HybridMergeResult, dict, dict, dict[str, Path]]:
    """Build Hybrid v1 entirely from sealed local artifacts."""
    paths = artifact_paths(output_dir)
    existing = [path for path in paths.values() if path.exists()]
    if existing:
        raise FileExistsError(
            "Hybrid artifacts already exist and will not be overwritten: "
            + ", ".join(str(path) for path in existing)
        )

    input_paths = {
        "dev": Path(dev_path),
        "reference_annotations": Path(annotations_path),
        "rule_predictions": Path(rule_predictions_path),
        "rule_evaluation": Path(rule_evaluation_path),
        "llm_no_context_predictions": Path(llm_no_context_predictions_path),
        "llm_no_context_evaluation": Path(llm_no_context_evaluation_path),
        "llm_with_context_predictions": Path(llm_with_context_predictions_path),
        "llm_with_context_evaluation": Path(llm_with_context_evaluation_path),
        "llm_with_context_config": Path(llm_with_context_config_path),
    }
    missing = [str(path) for path in input_paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing sealed input artifacts: " + ", ".join(missing))

    dev_frame = load_dev_dataset(dev_path)
    references = load_reference_annotations(annotations_path, dev_frame)
    rule_predictions = _load_predictions(rule_predictions_path)
    no_context_predictions = _load_predictions(llm_no_context_predictions_path)
    with_context_predictions = _load_predictions(
        llm_with_context_predictions_path
    )
    merge_result = merge_hybrid_predictions(
        rule_predictions,
        with_context_predictions,
    )

    predictions_by_method = {
        "rule_only": rule_predictions,
        "llm_no_context": no_context_predictions,
        "llm_with_context": with_context_predictions,
        "hybrid": merge_result.predictions,
    }
    comparison, evaluations = build_method_comparison(
        references,
        dev_frame,
        predictions_by_method,
    )

    sealed_evaluations = {
        "rule_only": _read_json(rule_evaluation_path),
        "llm_no_context": _read_json(llm_no_context_evaluation_path),
        "llm_with_context": _read_json(llm_with_context_evaluation_path),
    }
    for method, sealed in sealed_evaluations.items():
        if sealed["overall_micro"] != evaluations[method]["overall_micro"]:
            raise ValueError(
                f"Recomputed {method} metrics do not match the sealed evaluation"
            )

    paired = build_paired_analysis(
        references,
        rule_predictions,
        with_context_predictions,
        merge_result,
    )
    hybrid_evaluation = evaluations["hybrid"]
    hybrid_evaluation["context_sensitive_subset"] = comparison[
        "context_sensitive"
    ]["hybrid"]
    hybrid_evaluation["merge_diagnostics"] = {
        "llm_predictions_received": len(with_context_predictions),
        "llm_predictions_included": (
            len(with_context_predictions)
            - len(merge_result.llm_predictions_excluded_from_hybrid)
        ),
        "llm_predictions_excluded": len(
            merge_result.llm_predictions_excluded_from_hybrid
        ),
        "excluded_rule_addressable_count": sum(
            prediction.issue_type in RULE_ADDRESSABLE_ISSUE_TYPES
            for prediction in merge_result.llm_predictions_excluded_from_hybrid
        ),
        "excluded_unknown_count": sum(
            prediction.issue_type not in REGISTERED_ISSUE_TYPES
            for prediction in merge_result.llm_predictions_excluded_from_hybrid
        ),
        "excluded_predictions": [
            prediction.to_dict()
            for prediction in merge_result.llm_predictions_excluded_from_hybrid
        ],
        "merge_duplicate_predictions": merge_result.duplicate_predictions,
    }

    false_positive_keys = {
        (record["string_id"], record["issue_type"]): record
        for record in paired["hybrid_false_positives"]
    }
    attributed_false_positives = []
    for record in hybrid_evaluation["false_positives"]:
        item = dict(record)
        item["source_component"] = false_positive_keys[
            (item["string_id"], item["issue_type"])
        ]["source_component"]
        attributed_false_positives.append(item)

    bad_cases = {
        "false_positive_count": len(attributed_false_positives),
        "false_negative_count": len(hybrid_evaluation["false_negatives"]),
        "false_positive_source_counts": {
            "rule": sum(
                item["source_component"] == "rule"
                for item in attributed_false_positives
            ),
            "llm": sum(
                item["source_component"] == "llm"
                for item in attributed_false_positives
            ),
            "rule+llm": sum(
                item["source_component"] == "rule+llm"
                for item in attributed_false_positives
            ),
        },
        "false_positives": attributed_false_positives,
        "false_negatives": hybrid_evaluation["false_negatives"],
        "paired_analysis": paired,
        "duplicate_predictions": hybrid_evaluation["duplicate_predictions"],
        "unknown_prediction_types": hybrid_evaluation[
            "unknown_prediction_types"
        ],
        "llm_predictions_excluded_from_hybrid": hybrid_evaluation[
            "merge_diagnostics"
        ]["excluded_predictions"],
    }

    llm_config = _read_json(llm_with_context_config_path)
    config = {
        "experiment_id": EXPERIMENT_ID,
        "created_at_utc": datetime.now(UTC).isoformat(),
        "rule_component": "rule_baseline_v1",
        "llm_component": llm_config["experiment_id"],
        "llm_model": llm_config["model"],
        "llm_input_mode": llm_config["input_mode"],
        "hybrid_policy": (
            "all_rule_predictions__plus_llm_required_from_with_context_llm"
        ),
        "provider_calls": 0,
        "dataset": llm_config["dataset"],
        "dataset_item_count": llm_config["dataset_item_count"],
        "taxonomy_source": "src/j_gamelqa/taxonomy.py",
        "rule_addressable_issue_types": sorted(RULE_ADDRESSABLE_ISSUE_TYPES),
        "llm_required_issue_types": sorted(LLM_REQUIRED_ISSUE_TYPES),
        "evaluation_key": ["string_id", "issue_type"],
        "component_artifacts": {
            name: {
                "path": str(path.resolve()),
                "sha256": _sha256(path),
            }
            for name, path in input_paths.items()
        },
    }

    comparison["experiment"] = {
        "experiment_id": EXPERIMENT_ID,
        "hybrid_policy": config["hybrid_policy"],
        "provider_calls": 0,
    }
    comparison["paired_bad_cases"] = paired

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    _write_json(paths["config"], config)
    _write_json(
        paths["predictions"],
        [prediction.to_dict() for prediction in merge_result.predictions],
    )
    _write_json(paths["evaluation"], hybrid_evaluation)
    _write_json(paths["bad_cases"], bad_cases)
    _write_json(paths["comparison"], comparison)
    _write_comparison_csv(paths["comparison_csv"], comparison)
    return merge_result, hybrid_evaluation, comparison, paths


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build Hybrid v1 from sealed Rule and LLM artifacts."
    )
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "outputs")
    parser.add_argument("--dev", type=Path, default=PROJECT_ROOT / "data" / "dev.csv")
    parser.add_argument(
        "--annotations",
        type=Path,
        default=PROJECT_ROOT / "data" / "dev_annotations.csv",
    )
    args = parser.parse_args()
    outputs = args.output_dir
    merge_result, evaluation, comparison, paths = run_artifact_experiment(
        dev_path=args.dev,
        annotations_path=args.annotations,
        rule_predictions_path=outputs / "dev_rule_predictions.json",
        rule_evaluation_path=outputs / "dev_evaluation.json",
        llm_no_context_predictions_path=(
            outputs / "qwen35_9b_no_context_predictions.json"
        ),
        llm_no_context_evaluation_path=(
            outputs / "qwen35_9b_no_context_evaluation.json"
        ),
        llm_with_context_predictions_path=(
            outputs / "qwen35_9b_with_context_predictions.json"
        ),
        llm_with_context_evaluation_path=(
            outputs / "qwen35_9b_with_context_evaluation.json"
        ),
        llm_with_context_config_path=(
            outputs / "qwen35_9b_with_context_config.json"
        ),
        output_dir=outputs,
    )
    print(
        json.dumps(
            {
                "provider_calls": 0,
                "raw_hybrid_prediction_count": len(merge_result.predictions),
                "overall_micro": evaluation["overall_micro"],
                "hybrid_vs_rule": comparison["pairwise"][
                    "hybrid_vs_rule"
                ]["overall"],
                "artifacts": {name: str(path) for name, path in paths.items()},
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
