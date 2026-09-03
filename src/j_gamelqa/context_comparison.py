"""Controlled comparison of sealed no-context and with-context LLM runs."""

import argparse
import json
from pathlib import Path

from j_gamelqa.evaluate import calculate_subset_metrics
from j_gamelqa.io import load_dev_dataset, load_reference_annotations
from j_gamelqa.models import Issue
from j_gamelqa.taxonomy import REGISTERED_ISSUE_TYPES


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONTEXT_SENSITIVE_ISSUES = frozenset(
    {
        "keigo_mismatch",
        "first_person_mismatch",
        "character_voice_mismatch",
    }
)
METRIC_FIELDS = ("tp", "fp", "fn", "precision", "recall", "f1")
CONTROLLED_CONFIG_FIELDS = (
    "model",
    "provider",
    "provider_endpoint",
    "temperature",
    "thinking",
    "stream",
    "prompt_version",
    "parser_policy",
    "retry_policy",
    "structured_output",
    "timeout_seconds",
    "dataset",
    "dataset_item_count",
    "dev_path",
    "glossary_path",
    "annotations_path_for_evaluation_only",
)


def calculate_metric_delta(before: dict, after: dict) -> dict[str, float | int]:
    """Return With Context minus No Context for detection metrics."""
    return {
        field: after[field] - before[field]
        for field in METRIC_FIELDS
    }


def _prediction_keys(predictions: list[Issue]) -> set[tuple[str, str]]:
    return {
        (prediction.string_id, prediction.issue_type)
        for prediction in predictions
    }


def paired_detection_changes(
    reference_annotations,
    no_context_predictions: list[Issue],
    with_context_predictions: list[Issue],
) -> dict[str, list[dict[str, str]]]:
    """Identify paired improvements and regressions on identical samples."""
    reference_keys = {
        (str(row.string_id), str(row.issue_type))
        for row in reference_annotations.itertuples(index=False)
    }
    before_keys = _prediction_keys(no_context_predictions)
    after_keys = _prediction_keys(with_context_predictions)

    context_fixes = sorted((reference_keys & after_keys) - before_keys)
    context_regressions = sorted((reference_keys & before_keys) - after_keys)
    before_false_positives = before_keys - reference_keys
    after_false_positives = after_keys - reference_keys
    new_false_positives = sorted(after_false_positives - before_false_positives)
    resolved_false_positives = sorted(
        before_false_positives - after_false_positives
    )

    def records(keys, before_status, after_status):
        return [
            {
                "string_id": key[0],
                "issue_type": key[1],
                "before_status": before_status,
                "after_status": after_status,
            }
            for key in keys
        ]

    return {
        "context_fixes": records(context_fixes, "false_negative", "true_positive"),
        "context_regressions": records(
            context_regressions, "true_positive", "false_negative"
        ),
        "new_false_positives": records(
            new_false_positives, "not_predicted", "false_positive"
        ),
        "resolved_false_positives": records(
            resolved_false_positives, "false_positive", "not_predicted"
        ),
    }


def compare_context_experiments(
    reference_annotations,
    no_context_predictions: list[Issue],
    with_context_predictions: list[Issue],
    no_context_evaluation: dict,
    with_context_evaluation: dict,
    no_context_config: dict,
    with_context_config: dict,
) -> dict[str, object]:
    """Build the complete controlled comparison artifact."""
    controlled_settings = {
        field: {
            "no_context": no_context_config.get(field),
            "with_context": with_context_config.get(field),
            "same": no_context_config.get(field) == with_context_config.get(field),
        }
        for field in CONTROLLED_CONFIG_FIELDS
    }
    unintended_differences = [
        field
        for field, values in controlled_settings.items()
        if not values["same"]
    ]

    no_context_subset = calculate_subset_metrics(
        reference_annotations,
        no_context_predictions,
        CONTEXT_SENSITIVE_ISSUES,
    )
    with_context_subset = calculate_subset_metrics(
        reference_annotations,
        with_context_predictions,
        CONTEXT_SENSITIVE_ISSUES,
    )

    no_per_issue = {
        row["issue_type"]: row
        for row in no_context_evaluation["per_issue_type"]
    }
    with_per_issue = {
        row["issue_type"]: row
        for row in with_context_evaluation["per_issue_type"]
    }
    per_issue = []
    for issue_type in sorted(REGISTERED_ISSUE_TYPES):
        before = no_per_issue[issue_type]
        after = with_per_issue[issue_type]
        per_issue.append(
            {
                "issue_type": issue_type,
                "no_context": before,
                "with_context": after,
                "delta": {
                    "reference_count": (
                        after["reference_count"] - before["reference_count"]
                    ),
                    "prediction_count": (
                        after["prediction_count"] - before["prediction_count"]
                    ),
                    **calculate_metric_delta(before, after),
                },
            }
        )

    return {
        "experiments": {
            "no_context": no_context_config,
            "with_context": with_context_config,
        },
        "controlled_experiment_check": {
            "intended_variable": "input_mode",
            "no_context_input_mode": no_context_config.get("input_mode"),
            "with_context_input_mode": with_context_config.get("input_mode"),
            "controlled_settings": controlled_settings,
            "unintended_differences": unintended_differences,
        },
        "overall": {
            "no_context": no_context_evaluation["overall_micro"],
            "with_context": with_context_evaluation["overall_micro"],
            "delta": calculate_metric_delta(
                no_context_evaluation["overall_micro"],
                with_context_evaluation["overall_micro"],
            ),
        },
        "llm_required": {
            "no_context": no_context_evaluation["llm_required_micro"],
            "with_context": with_context_evaluation["llm_required_micro"],
            "delta": calculate_metric_delta(
                no_context_evaluation["llm_required_micro"],
                with_context_evaluation["llm_required_micro"],
            ),
        },
        "context_sensitive_subset": {
            "issue_types": sorted(CONTEXT_SENSITIVE_ISSUES),
            "no_context": no_context_subset,
            "with_context": with_context_subset,
            "delta": calculate_metric_delta(
                no_context_subset, with_context_subset
            ),
        },
        "rule_addressable": {
            "no_context": no_context_evaluation["rule_addressable_micro"],
            "with_context": with_context_evaluation["rule_addressable_micro"],
            "delta": calculate_metric_delta(
                no_context_evaluation["rule_addressable_micro"],
                with_context_evaluation["rule_addressable_micro"],
            ),
        },
        "per_issue": per_issue,
        "paired_changes": paired_detection_changes(
            reference_annotations,
            no_context_predictions,
            with_context_predictions,
        ),
        "protocol": {
            "no_context": no_context_evaluation["protocol_metrics"],
            "with_context": with_context_evaluation["protocol_metrics"],
        },
    }


def _load_json(path: str | Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _load_predictions(path: str | Path) -> list[Issue]:
    return [Issue(**record) for record in _load_json(path)]


def write_context_comparison(
    output_path: str | Path,
    dev_path: str | Path,
    annotations_path: str | Path,
    no_context_paths: dict[str, Path],
    with_context_paths: dict[str, Path],
) -> dict[str, object]:
    """Read two sealed experiments and write one non-overwriting comparison."""
    destination = Path(output_path)
    if destination.exists():
        raise FileExistsError(
            f"context comparison artifact already exists: {destination}"
        )
    dev_frame = load_dev_dataset(dev_path)
    reference_annotations = load_reference_annotations(
        annotations_path, dev_frame
    )
    comparison = compare_context_experiments(
        reference_annotations,
        _load_predictions(no_context_paths["predictions"]),
        _load_predictions(with_context_paths["predictions"]),
        _load_json(no_context_paths["evaluation"]),
        _load_json(with_context_paths["evaluation"]),
        _load_json(no_context_paths["config"]),
        _load_json(with_context_paths["config"]),
    )
    destination.write_text(
        json.dumps(comparison, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return comparison


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare sealed Qwen3.5-9B context-control runs."
    )
    parser.add_argument(
        "--output-dir", type=Path, default=PROJECT_ROOT / "outputs"
    )
    parser.add_argument(
        "--dev", type=Path, default=PROJECT_ROOT / "data" / "dev.csv"
    )
    parser.add_argument(
        "--annotations",
        type=Path,
        default=PROJECT_ROOT / "data" / "dev_annotations.csv",
    )
    args = parser.parse_args()

    no_context = {
        "config": args.output_dir / "qwen35_9b_no_context_config.json",
        "predictions": args.output_dir
        / "qwen35_9b_no_context_predictions.json",
        "evaluation": args.output_dir
        / "qwen35_9b_no_context_evaluation.json",
    }
    with_context = {
        "config": args.output_dir / "qwen35_9b_with_context_config.json",
        "predictions": args.output_dir
        / "qwen35_9b_with_context_predictions.json",
        "evaluation": args.output_dir
        / "qwen35_9b_with_context_evaluation.json",
    }
    output_path = args.output_dir / "qwen35_9b_context_comparison.json"
    comparison = write_context_comparison(
        output_path,
        args.dev,
        args.annotations,
        no_context,
        with_context,
    )
    print(
        json.dumps(
            {
                "output": str(output_path),
                "overall_delta": comparison["overall"]["delta"],
                "llm_required_delta": comparison["llm_required"]["delta"],
                "context_sensitive_delta": comparison[
                    "context_sensitive_subset"
                ]["delta"],
                "paired_change_counts": {
                    name: len(items)
                    for name, items in comparison["paired_changes"].items()
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
