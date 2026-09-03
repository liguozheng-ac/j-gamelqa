"""Validated tabular input loading for J-GameLQA."""

import json
import re
from pathlib import Path

import pandas as pd


REQUIRED_DATASET_FIELDS = (
    "string_id",
    "source_zh",
    "target_ja",
    "string_type",
    "speaker",
    "addressee",
    "scene",
    "relationship",
    "context_before",
    "context_after",
    "max_length",
    "expected_issue",
    "expected_severity",
)

REQUIRED_GLOSSARY_FIELDS = ("source_term", "approved_ja", "forbidden_ja")

DEV_INPUT_FIELDS = (
    "string_id",
    "source_zh",
    "target_ja",
    "string_type",
    "speaker",
    "addressee",
    "scene",
    "relationship",
    "context_before",
    "context_after",
    "max_length",
)

REFERENCE_ANNOTATION_FIELDS = (
    "annotation_id",
    "string_id",
    "issue_type",
    "severity",
    "source_span",
    "target_span",
    "evidence",
    "annotation_note",
)

NON_EMPTY_DEV_FIELDS = (
    "string_id",
    "source_zh",
    "target_ja",
    "string_type",
    "speaker",
    "addressee",
    "scene",
    "relationship",
    "max_length",
)

NON_EMPTY_ANNOTATION_FIELDS = (
    "annotation_id",
    "string_id",
    "issue_type",
    "severity",
)

VALID_SEVERITIES = frozenset({"minor", "major", "critical"})
ANSWER_LEAKAGE_FIELDS = frozenset(
    {"expected_issue", "expected_severity", "answer", "label"}
)
IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


def _validate_columns(columns, required_fields, dataset_name: str) -> None:
    missing = [field for field in required_fields if field not in columns]
    if missing:
        raise ValueError(f"{dataset_name} is missing required fields: {', '.join(missing)}")


def _validate_non_empty(frame: pd.DataFrame, fields, dataset_name: str) -> None:
    for field in fields:
        empty_rows = frame.index[frame[field].str.strip() == ""].tolist()
        if empty_rows:
            raise ValueError(
                f"{dataset_name} field {field!r} contains empty values at rows: "
                f"{[row + 2 for row in empty_rows]}"
            )


def _validate_identifiers(frame: pd.DataFrame, field: str, dataset_name: str) -> None:
    invalid = [value for value in frame[field] if not IDENTIFIER_PATTERN.fullmatch(value)]
    if invalid:
        raise ValueError(f"{dataset_name} contains invalid {field} values: {invalid}")


def load_dataset(path: str | Path) -> pd.DataFrame:
    """Load localization records and reject an incomplete schema."""
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    _validate_columns(frame.columns, REQUIRED_DATASET_FIELDS, "dataset")
    if frame["string_id"].duplicated().any():
        duplicates = frame.loc[frame["string_id"].duplicated(), "string_id"].tolist()
        raise ValueError(f"dataset contains duplicate string_id values: {duplicates}")
    return frame


def _load_system_input_dataset(
    path: str | Path, dataset_name: str
) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    _validate_columns(frame.columns, DEV_INPUT_FIELDS, dataset_name)

    leaked_fields = sorted(ANSWER_LEAKAGE_FIELDS.intersection(frame.columns))
    if leaked_fields:
        raise ValueError(
            f"{dataset_name} must not contain answer leakage fields: "
            + ", ".join(leaked_fields)
        )

    _validate_non_empty(frame, NON_EMPTY_DEV_FIELDS, dataset_name)
    _validate_identifiers(frame, "string_id", dataset_name)
    if frame["string_id"].duplicated().any():
        duplicates = frame.loc[frame["string_id"].duplicated(), "string_id"].tolist()
        raise ValueError(
            f"{dataset_name} contains duplicate string_id values: {duplicates}"
        )

    invalid_lengths = []
    for string_id, raw_limit in zip(frame["string_id"], frame["max_length"]):
        try:
            if int(raw_limit) <= 0:
                invalid_lengths.append(string_id)
        except ValueError:
            invalid_lengths.append(string_id)
    if invalid_lengths:
        raise ValueError(
            f"{dataset_name} contains invalid max_length values for: {invalid_lengths}"
        )
    return frame


def load_dev_dataset(path: str | Path) -> pd.DataFrame:
    """Load development inputs without allowing answer leakage."""
    return _load_system_input_dataset(path, "dev dataset")


def load_test_dataset(path: str | Path) -> pd.DataFrame:
    """Load held-out test inputs without allowing answer leakage."""
    return _load_system_input_dataset(path, "test dataset")


def load_reference_annotations(
    path: str | Path, dev_frame: pd.DataFrame
) -> pd.DataFrame:
    """Load validated reference annotations for one benchmark split."""
    from j_gamelqa.taxonomy import REGISTERED_ISSUE_TYPES

    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    _validate_columns(
        frame.columns, REFERENCE_ANNOTATION_FIELDS, "reference annotations"
    )
    _validate_non_empty(frame, NON_EMPTY_ANNOTATION_FIELDS, "reference annotations")
    _validate_identifiers(frame, "annotation_id", "reference annotations")
    _validate_identifiers(frame, "string_id", "reference annotations")

    if frame["annotation_id"].duplicated().any():
        duplicates = frame.loc[
            frame["annotation_id"].duplicated(), "annotation_id"
        ].tolist()
        raise ValueError(
            f"reference annotations contain duplicate annotation_id values: {duplicates}"
        )

    known_string_ids = set(dev_frame["string_id"])
    unknown_string_ids = sorted(set(frame["string_id"]) - known_string_ids)
    if unknown_string_ids:
        raise ValueError(
            "reference annotations contain string_id values missing from dev dataset: "
            + ", ".join(unknown_string_ids)
        )

    duplicate_keys = frame.duplicated(subset=["string_id", "issue_type"], keep=False)
    if duplicate_keys.any():
        keys = sorted(
            {
                (row.string_id, row.issue_type)
                for row in frame.loc[duplicate_keys, ["string_id", "issue_type"]].itertuples(
                    index=False
                )
            }
        )
        raise ValueError(
            f"reference annotations contain duplicate detection keys: {keys}"
        )

    unknown_types = sorted(set(frame["issue_type"]) - REGISTERED_ISSUE_TYPES)
    if unknown_types:
        raise ValueError(
            "unknown reference issue_type values: " + ", ".join(unknown_types)
        )

    invalid_severities = sorted(set(frame["severity"]) - VALID_SEVERITIES)
    if invalid_severities:
        raise ValueError(
            "reference annotations contain invalid severity values: "
            + ", ".join(invalid_severities)
        )

    for row_number, raw_evidence in enumerate(frame["evidence"], start=2):
        if not raw_evidence.strip():
            continue
        try:
            json.loads(raw_evidence)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"reference annotations contain invalid evidence JSON at row {row_number}"
            ) from exc
    return frame


def load_glossary(path: str | Path) -> list[dict[str, str]]:
    """Load the exact-match glossary and validate its schema."""
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    _validate_columns(frame.columns, REQUIRED_GLOSSARY_FIELDS, "glossary")
    return frame.loc[:, REQUIRED_GLOSSARY_FIELDS].to_dict(orient="records")
