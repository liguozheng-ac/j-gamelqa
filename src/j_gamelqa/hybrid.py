"""Transparent Rule + Japanese LLM prediction merge for Hybrid v1."""

from collections import Counter
from dataclasses import dataclass

from j_gamelqa.models import Issue
from j_gamelqa.taxonomy import LLM_REQUIRED_ISSUE_TYPES


@dataclass(slots=True)
class HybridMergeResult:
    """Merged predictions plus LLM exclusions and duplicate diagnostics."""

    predictions: list[Issue]
    llm_predictions_excluded_from_hybrid: list[Issue]
    duplicate_predictions: list[dict[str, object]]


def merge_hybrid_predictions(
    rule_predictions: list[Issue], llm_predictions: list[Issue]
) -> HybridMergeResult:
    """Keep all rules and only the LLM-required part of the LLM output."""
    included_llm_predictions = [
        prediction
        for prediction in llm_predictions
        if prediction.issue_type in LLM_REQUIRED_ISSUE_TYPES
    ]
    excluded_llm_predictions = [
        prediction
        for prediction in llm_predictions
        if prediction.issue_type not in LLM_REQUIRED_ISSUE_TYPES
    ]
    predictions = [*rule_predictions, *included_llm_predictions]

    key_counts = Counter(
        (prediction.string_id, prediction.issue_type)
        for prediction in predictions
    )
    duplicate_predictions = [
        {"string_id": key[0], "issue_type": key[1], "count": count}
        for key, count in sorted(key_counts.items())
        if count > 1
    ]

    return HybridMergeResult(
        predictions=predictions,
        llm_predictions_excluded_from_hybrid=excluded_llm_predictions,
        duplicate_predictions=duplicate_predictions,
    )
