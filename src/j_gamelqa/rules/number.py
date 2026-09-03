"""Deterministic checks for Arabic numbers, decimals, and percentages."""

import re

from j_gamelqa.models import Issue
from j_gamelqa.rules.placeholder import PLACEHOLDER_PATTERN


NUMBER_PATTERN = re.compile(r"[-+]?\d+(?:\.\d+)?%?")


def extract_numbers(text: str) -> list[str]:
    """Extract supported numbers without reading digits inside Placeholders."""
    text_without_placeholders = PLACEHOLDER_PATTERN.sub("", text)
    return NUMBER_PATTERN.findall(text_without_placeholders)


def compare_numbers(source_text: str, target_text: str) -> dict[str, list[str]]:
    """Compare number values while allowing them to be reordered."""
    source_numbers = extract_numbers(source_text)
    unmatched_target = extract_numbers(target_text)
    missing = []

    for number in source_numbers:
        if number in unmatched_target:
            unmatched_target.remove(number)
        else:
            missing.append(number)

    return {"missing": missing, "extra": unmatched_target}


def check_number_issues(record: dict[str, object]) -> list[Issue]:
    comparison = compare_numbers(str(record["source_zh"]), str(record["target_ja"]))
    missing = comparison["missing"]
    extra = comparison["extra"]
    if not missing and not extra:
        return []

    if missing and extra:
        issue_type = "number_mismatch"
        severity = "major"
    elif missing:
        issue_type = "number_missing"
        severity = "major"
    else:
        issue_type = "number_extra"
        severity = "minor"

    return [
        Issue(
            string_id=str(record["string_id"]),
            checker="number",
            issue_type=issue_type,
            severity=severity,
            message="源文与日语译文中的数字、数值或百分比不一致。",
            source_span=", ".join(missing) or None,
            target_span=", ".join(extra) or None,
            evidence={
                "source_numbers": extract_numbers(str(record["source_zh"])),
                "target_numbers": extract_numbers(str(record["target_ja"])),
                "missing": missing,
                "extra": extra,
            },
        )
    ]
