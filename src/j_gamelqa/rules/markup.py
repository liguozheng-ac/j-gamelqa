"""Lightweight integrity checks for common game-localization markup tags."""

import re

from j_gamelqa.models import Issue


MARKUP_PATTERN = re.compile(r"</?[A-Za-z][^<>]*>")


def extract_markup(text: str) -> list[str]:
    return MARKUP_PATTERN.findall(text)


def has_malformed_markup(text: str) -> bool:
    """Detect leftover angle brackets after removing valid-looking tags."""
    remaining_text = MARKUP_PATTERN.sub("", text)
    return "<" in remaining_text or ">" in remaining_text


def check_markup_issues(record: dict[str, object]) -> list[Issue]:
    source_text = str(record["source_zh"])
    target_text = str(record["target_ja"])
    source_tags = extract_markup(source_text)
    target_tags = extract_markup(target_text)

    if has_malformed_markup(target_text) and not has_malformed_markup(source_text):
        return [
            Issue(
                string_id=str(record["string_id"]),
                checker="markup",
                issue_type="markup_malformed",
                severity="major",
                message="日语译文中存在明显损坏的技术标签。",
                target_span=target_text,
                evidence={"source_tags": source_tags, "target_tags": target_tags},
            )
        ]

    unmatched_target = target_tags.copy()
    missing = []
    for tag in source_tags:
        if tag in unmatched_target:
            unmatched_target.remove(tag)
        else:
            missing.append(tag)

    extra = unmatched_target
    if missing and extra:
        issue_type = "markup_modified"
    elif missing:
        issue_type = "markup_missing"
    elif extra:
        issue_type = "markup_extra"
    elif source_tags != target_tags:
        issue_type = "markup_order_mismatch"
    else:
        return []

    return [
        Issue(
            string_id=str(record["string_id"]),
            checker="markup",
            issue_type=issue_type,
            severity="major",
            message="源文与日语译文中的技术标签不一致。",
            source_span=", ".join(missing) or None,
            target_span=", ".join(extra) or None,
            evidence={
                "source_tags": source_tags,
                "target_tags": target_tags,
                "missing": missing,
                "extra": extra,
            },
        )
    ]
