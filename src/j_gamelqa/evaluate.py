"""Benchmark v1 issue-detection evaluation for J-GameLQA."""

import argparse
import json
from collections import defaultdict
from pathlib import Path

import pandas as pd

from j_gamelqa.io import (
    load_dev_dataset,
    load_glossary,
    load_reference_annotations,
)
from j_gamelqa.models import Issue
from j_gamelqa.rule_engine import evaluate_dataframe
from j_gamelqa.taxonomy import (
    LLM_REQUIRED_ISSUE_TYPES,
    REGISTERED_ISSUE_TYPES,
    RULE_ADDRESSABLE_ISSUE_TYPES,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DetectionKey = tuple[str, str]


def _safe_divide(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _calculate_metrics(
    reference_keys: set[DetectionKey], prediction_keys: set[DetectionKey]
) -> dict[str, float | int]:
    true_positives = len(reference_keys & prediction_keys)
    false_positives = len(prediction_keys - reference_keys)
    false_negatives = len(reference_keys - prediction_keys)
    precision = _safe_divide(true_positives, true_positives + false_positives)
    recall = _safe_divide(true_positives, true_positives + false_negatives)
    f1 = _safe_divide(2 * precision * recall, precision + recall)
    return {
        "tp": true_positives,
        "fp": false_positives,
        "fn": false_negatives,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def _reference_map(reference_annotations: pd.DataFrame) -> dict[DetectionKey, dict]:
    references = {}
    for record in reference_annotations.to_dict(orient="records"):
        key = (str(record["string_id"]), str(record["issue_type"]))
        if key in references:
            raise ValueError(f"duplicate reference detection key: {key}")
        references[key] = record
    return references


def _prediction_groups(
    predictions: list[Issue],
) -> dict[DetectionKey, list[Issue]]:
    groups = defaultdict(list)
    for issue in predictions:
        groups[(issue.string_id, issue.issue_type)].append(issue)
    return dict(groups)


def calculate_subset_metrics(
    reference_annotations: pd.DataFrame,
    predictions: list[Issue],
    issue_types: set[str] | frozenset[str],
) -> dict[str, float | int]:
    """Calculate detection metrics for one explicit taxonomy subset."""
    reference_keys = {
        key for key in _reference_map(reference_annotations) if key[1] in issue_types
    }
    prediction_keys = {
        key for key in _prediction_groups(predictions) if key[1] in issue_types
    }
    return _calculate_metrics(reference_keys, prediction_keys)


def _context_map(dev_frame: pd.DataFrame | None) -> dict[str, dict[str, str]]:
    if dev_frame is None:
        return {}
    available = [
        field
        for field in ("string_id", "source_zh", "target_ja")
        if field in dev_frame.columns
    ]
    if "string_id" not in available:
        return {}
    return {
        str(record["string_id"]): record
        for record in dev_frame.loc[:, available].to_dict(orient="records")
    }


def _reference_diagnostic(record: dict, context: dict[str, str]) -> dict:
    diagnostic = dict(record)
    raw_evidence = diagnostic.get("evidence", "")
    if isinstance(raw_evidence, str) and raw_evidence.strip():
        diagnostic["evidence"] = json.loads(raw_evidence)
    diagnostic.update(context)
    return diagnostic


def evaluate_detections(
    reference_annotations: pd.DataFrame,
    predictions: list[Issue],
    dev_frame: pd.DataFrame | None = None,
) -> dict:
    """Match detection keys and return metrics plus engineering diagnostics."""
    references = _reference_map(reference_annotations)
    prediction_groups = _prediction_groups(predictions)
    reference_keys = set(references)
    prediction_keys = set(prediction_groups)
    contexts = _context_map(dev_frame)

    rule_reference_keys = {
        key for key in reference_keys if key[1] in RULE_ADDRESSABLE_ISSUE_TYPES
    }
    rule_prediction_keys = {
        key for key in prediction_keys if key[1] in RULE_ADDRESSABLE_ISSUE_TYPES
    }
    llm_reference_keys = {
        key for key in reference_keys if key[1] in LLM_REQUIRED_ISSUE_TYPES
    }
    llm_prediction_keys = {
        key for key in prediction_keys if key[1] in LLM_REQUIRED_ISSUE_TYPES
    }

    seen_issue_types = {key[1] for key in reference_keys | prediction_keys}
    per_issue_type = []
    for issue_type in sorted(REGISTERED_ISSUE_TYPES | seen_issue_types):
        type_reference_keys = {key for key in reference_keys if key[1] == issue_type}
        type_prediction_keys = {key for key in prediction_keys if key[1] == issue_type}
        per_issue_type.append(
            {
                "issue_type": issue_type,
                "reference_count": len(type_reference_keys),
                "prediction_count": len(type_prediction_keys),
                **_calculate_metrics(type_reference_keys, type_prediction_keys),
            }
        )

    false_positive_keys = sorted(prediction_keys - reference_keys)
    false_negative_keys = sorted(reference_keys - prediction_keys)
    false_positives = []
    for key in false_positive_keys:
        record = prediction_groups[key][0].to_dict()
        record.update(contexts.get(key[0], {}))
        false_positives.append(record)

    false_negatives = [
        _reference_diagnostic(references[key], contexts.get(key[0], {}))
        for key in false_negative_keys
    ]

    duplicate_predictions = [
        {"string_id": key[0], "issue_type": key[1], "count": len(group)}
        for key, group in sorted(prediction_groups.items())
        if len(group) > 1
    ]

    unknown_prediction_keys = sorted(
        key for key in prediction_keys if key[1] not in REGISTERED_ISSUE_TYPES
    )
    unknown_prediction_types = sorted({key[1] for key in unknown_prediction_keys})
    unknown_prediction_occurrences = [
        {
            "string_id": key[0],
            "issue_type": key[1],
            "count": len(prediction_groups[key]),
        }
        for key in unknown_prediction_keys
    ]

    return {
        "matching_key": ["string_id", "issue_type"],
        "reference_detection_count": len(reference_keys),
        "raw_prediction_count": len(predictions),
        "unique_prediction_detection_count": len(prediction_keys),
        "overall_micro": _calculate_metrics(reference_keys, prediction_keys),
        "rule_addressable_micro": _calculate_metrics(
            rule_reference_keys, rule_prediction_keys
        ),
        "llm_required_micro": _calculate_metrics(
            llm_reference_keys, llm_prediction_keys
        ),
        "per_issue_type": per_issue_type,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "duplicate_predictions": duplicate_predictions,
        "unknown_prediction_types": unknown_prediction_types,
        "unknown_prediction_occurrences": unknown_prediction_occurrences,
    }


def run_end_to_end(
    dev_path: str | Path,
    annotations_path: str | Path,
    glossary_path: str | Path,
    output_dir: str | Path,
) -> tuple[list[Issue], dict, dict[str, Path]]:
    """Run rules, evaluate predictions, and persist reproducible artifacts."""
    dev_frame = load_dev_dataset(dev_path)
    reference_annotations = load_reference_annotations(annotations_path, dev_frame)
    glossary = load_glossary(glossary_path)
    predictions = evaluate_dataframe(dev_frame, glossary)
    result = evaluate_detections(reference_annotations, predictions, dev_frame)

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    paths = {
        "predictions": destination / "dev_rule_predictions.json",
        "evaluation": destination / "dev_evaluation.json",
    }
    paths["predictions"].write_text(
        json.dumps(
            [prediction.to_dict() for prediction in predictions],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    paths["evaluation"].write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return predictions, result, paths


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the J-GameLQA synthetic development benchmark."
    )
    parser.add_argument("--dev", type=Path, default=PROJECT_ROOT / "data" / "dev.csv")
    parser.add_argument(
        "--annotations",
        type=Path,
        default=PROJECT_ROOT / "data" / "dev_annotations.csv",
    )
    parser.add_argument(
        "--glossary", type=Path, default=PROJECT_ROOT / "data" / "glossary.csv"
    )
    parser.add_argument(
        "--output-dir", type=Path, default=PROJECT_ROOT / "outputs"
    )
    args = parser.parse_args()

    predictions, result, paths = run_end_to_end(
        args.dev, args.annotations, args.glossary, args.output_dir
    )
    print(
        json.dumps(
            {
                "prediction_count": len(predictions),
                "overall_micro": result["overall_micro"],
                "rule_addressable_micro": result["rule_addressable_micro"],
                "reports": {name: str(path) for name, path in paths.items()},
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
