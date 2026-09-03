"""Static validation for the frozen development and held-out test splits."""

import argparse
import hashlib
import json
import unicodedata
from collections import Counter
from pathlib import Path

import pandas as pd

from j_gamelqa.io import (
    ANSWER_LEAKAGE_FIELDS,
    load_dev_dataset,
    load_reference_annotations,
    load_test_dataset,
)
from j_gamelqa.taxonomy import (
    LLM_REQUIRED_ISSUE_TYPES,
    REGISTERED_ISSUE_TYPES,
    RULE_ADDRESSABLE_ISSUE_TYPES,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LEAKAGE_TEXT_FIELDS = (
    "source_zh",
    "target_ja",
    "context_before",
    "context_after",
)


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def normalize_for_leakage(text: str) -> str:
    """Normalize case, Unicode width, line endings, and surrounding whitespace."""
    normalized = unicodedata.normalize("NFKC", str(text))
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    normalized = "\n".join(line.strip() for line in normalized.split("\n"))
    return normalized.strip().casefold()


def _cross_split_matches(
    development: pd.DataFrame,
    held_out_test: pd.DataFrame,
    field: str,
    normalizer,
) -> list[dict[str, str]]:
    development_values = {}
    for row in development.loc[:, ["string_id", field]].itertuples(index=False):
        value = normalizer(row[1])
        development_values.setdefault(value, []).append(str(row.string_id))

    matches = []
    for row in held_out_test.loc[:, ["string_id", field]].itertuples(index=False):
        value = normalizer(row[1])
        for development_id in development_values.get(value, []):
            matches.append(
                {
                    "field": field,
                    "development_id": development_id,
                    "test_id": str(row.string_id),
                }
            )
    return matches


def check_split_leakage(
    development: pd.DataFrame,
    held_out_test: pd.DataFrame,
) -> dict[str, list[dict[str, str]]]:
    """Report exact and normalized cross-split text duplicates."""
    exact = []
    normalized = []
    for field in LEAKAGE_TEXT_FIELDS:
        exact.extend(
            _cross_split_matches(development, held_out_test, field, lambda value: value)
        )
        normalized.extend(
            _cross_split_matches(
                development,
                held_out_test,
                field,
                normalize_for_leakage,
            )
        )
    return {"exact_duplicates": exact, "normalized_duplicates": normalized}


def _load_manifest(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_benchmark_splits(
    *,
    dev_path: str | Path,
    dev_annotations_path: str | Path,
    test_path: str | Path,
    test_annotations_path: str | Path,
    manifest_path: str | Path,
) -> dict:
    """Validate split structure and composition without running any QA system."""
    development = load_dev_dataset(dev_path)
    development_annotations = load_reference_annotations(
        dev_annotations_path, development
    )
    held_out_test = load_test_dataset(test_path)
    test_annotations = load_reference_annotations(
        test_annotations_path, held_out_test
    )
    manifest = _load_manifest(manifest_path)
    test_manifest = manifest["held_out_test"]

    expected_test_ids = {f"TEST_{number:03d}" for number in range(1, 61)}
    actual_test_ids = set(held_out_test["string_id"])
    if actual_test_ids != expected_test_ids:
        raise ValueError("held-out test IDs must be exactly TEST_001 through TEST_060")

    type_counts = Counter(test_annotations["issue_type"])
    annotated_ids = set(test_annotations["string_id"])
    per_string_counts = Counter(test_annotations["string_id"])
    clean_ids = actual_test_ids - annotated_ids
    single_issue_ids = {
        string_id for string_id, count in per_string_counts.items() if count == 1
    }
    multi_issue_ids = {
        string_id for string_id, count in per_string_counts.items() if count >= 2
    }
    rule_reference_count = sum(
        type_counts[issue_type] for issue_type in RULE_ADDRESSABLE_ISSUE_TYPES
    )
    llm_reference_count = sum(
        type_counts[issue_type] for issue_type in LLM_REQUIRED_ISSUE_TYPES
    )
    context_reference_count = sum(
        type_counts[issue_type]
        for issue_type in {
            "keigo_mismatch",
            "first_person_mismatch",
            "character_voice_mismatch",
        }
    )

    if set(type_counts) != REGISTERED_ISSUE_TYPES:
        raise ValueError("held-out test must cover all registered issue types")
    if any(
        type_counts[issue_type] < 2
        for issue_type in RULE_ADDRESSABLE_ISSUE_TYPES
    ):
        raise ValueError("every Rule-addressable type requires at least 2 references")
    if any(
        type_counts[issue_type] < 4 for issue_type in LLM_REQUIRED_ISSUE_TYPES
    ):
        raise ValueError("every LLM-required type requires at least 4 references")

    expected_composition = {
        "samples": len(held_out_test),
        "reference_detections": len(test_annotations),
        "clean_samples": len(clean_ids),
        "single_issue_samples": len(single_issue_ids),
        "multi_issue_samples": len(multi_issue_ids),
        "rule_references": rule_reference_count,
        "llm_required_references": llm_reference_count,
        "context_sensitive_references": context_reference_count,
    }
    for field, actual in expected_composition.items():
        if test_manifest[field] != actual:
            raise ValueError(
                f"manifest {field}={test_manifest[field]} does not match data {actual}"
            )

    if set(test_manifest["clean_ids"]) != clean_ids:
        raise ValueError("manifest clean_ids do not match annotation-free samples")
    if set(test_manifest["multi_issue_ids"]) != multi_issue_ids:
        raise ValueError("manifest multi_issue_ids do not match annotations")
    if len(test_manifest["hard_negative_ids"]) < 10:
        raise ValueError("held-out test requires at least 10 hard-negative samples")
    if not set(test_manifest["hard_negative_ids"]) <= clean_ids:
        raise ValueError("hard-negative IDs must be annotation-free clean samples")
    if len(test_manifest["context_sensitive_ids"]) < 15:
        raise ValueError("held-out test requires at least 15 context-sensitive samples")
    if not set(test_manifest["context_sensitive_ids"]) <= actual_test_ids:
        raise ValueError("manifest contains unknown context-sensitive IDs")

    if ANSWER_LEAKAGE_FIELDS.intersection(held_out_test.columns):
        raise ValueError("held-out test input contains answer leakage columns")

    leakage = check_split_leakage(development, held_out_test)
    if leakage["exact_duplicates"] or leakage["normalized_duplicates"]:
        raise ValueError("development/test leakage check found duplicate text")

    recorded_hashes = test_manifest["sha256"]
    actual_hashes = {
        "test.csv": sha256_file(test_path),
        "test_annotations.csv": sha256_file(test_annotations_path),
    }
    if recorded_hashes != actual_hashes:
        raise ValueError("held-out test files no longer match frozen manifest hashes")

    return {
        "development": {
            "samples": len(development),
            "reference_detections": len(development_annotations),
        },
        "held_out_test": {
            **expected_composition,
            "context_sensitive_samples": len(
                test_manifest["context_sensitive_ids"]
            ),
            "issue_coverage": dict(sorted(type_counts.items())),
        },
        "leakage": {
            "exact_duplicate_count": len(leakage["exact_duplicates"]),
            "normalized_duplicate_count": len(
                leakage["normalized_duplicates"]
            ),
        },
        "static_validation_only": True,
        "provider_calls": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate frozen development/test benchmark splits without scoring."
    )
    parser.add_argument("--dev", type=Path, default=PROJECT_ROOT / "data" / "dev.csv")
    parser.add_argument(
        "--dev-annotations",
        type=Path,
        default=PROJECT_ROOT / "data" / "dev_annotations.csv",
    )
    parser.add_argument("--test", type=Path, default=PROJECT_ROOT / "data" / "test.csv")
    parser.add_argument(
        "--test-annotations",
        type=Path,
        default=PROJECT_ROOT / "data" / "test_annotations.csv",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=PROJECT_ROOT / "data" / "benchmark_manifest.json",
    )
    args = parser.parse_args()
    result = validate_benchmark_splits(
        dev_path=args.dev,
        dev_annotations_path=args.dev_annotations,
        test_path=args.test,
        test_annotations_path=args.test_annotations,
        manifest_path=args.manifest,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
