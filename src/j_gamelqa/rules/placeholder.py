"""Minimal Placeholder checks for the early J-GameLQA prototype."""

import re

from j_gamelqa.models import Issue


PLACEHOLDER_PATTERN = re.compile(
    r"\{[A-Za-z_][A-Za-z0-9_]*\}|%\([A-Za-z_][A-Za-z0-9_]*\)[sd]"
)


def extract_placeholders(text: str) -> list[str]:
    """Return all supported Placeholders in the order they appear."""
    return PLACEHOLDER_PATTERN.findall(text)


def compare_placeholders(source_text: str, target_text: str) -> dict[str, list[str]]:
    """Return Placeholders missing from or added to the target text."""
    source_placeholders = extract_placeholders(source_text)
    unmatched_target = extract_placeholders(target_text)
    missing = []

    for placeholder in source_placeholders:
        if placeholder in unmatched_target:
            unmatched_target.remove(placeholder)
        else:
            missing.append(placeholder)

    return {
        "missing": missing,
        "extra": unmatched_target,
    }


def check_placeholder_issue(source_text: str, target_text: str) -> dict[str, object]:
    """Classify the Placeholder difference between source and target text."""
    comparison = compare_placeholders(source_text, target_text)
    missing = comparison["missing"]
    extra = comparison["extra"]

    if missing and extra:
        issue_type = "placeholder_modified"
    elif missing:
        issue_type = "placeholder_missing"
    elif extra:
        issue_type = "placeholder_extra"
    else:
        issue_type = "none"

    return {
        "has_issue": issue_type != "none",
        "issue_type": issue_type,
        "missing": missing,
        "extra": extra,
    }


def check_placeholder_issues(record: dict[str, object]) -> list[Issue]:
    """Return a unified Issue when a record changes its Placeholders."""
    result = check_placeholder_issue(
        str(record["source_zh"]), str(record["target_ja"])
    )
    issue_type = str(result["issue_type"])
    if issue_type == "none":
        return []

    missing = list(result["missing"])
    extra = list(result["extra"])
    severity = "minor" if issue_type == "placeholder_extra" else "major"

    return [
        Issue(
            string_id=str(record["string_id"]),
            checker="placeholder",
            issue_type=issue_type,
            severity=severity,
            message="源文与日语译文的 Placeholder 不一致。",
            source_span=", ".join(missing) or None,
            target_span=", ".join(extra) or None,
            evidence={"missing": missing, "extra": extra},
        )
    ]
