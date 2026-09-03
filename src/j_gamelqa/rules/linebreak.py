"""Checks for required line-break count changes."""

from j_gamelqa.models import Issue


def count_linebreaks(text: str) -> dict[str, int]:
    """Count both real newlines and literal backslash-n tokens."""
    return {
        "actual_newlines": text.count("\n"),
        "escaped_newlines": text.count("\\n"),
    }


def check_linebreak_issues(record: dict[str, object]) -> list[Issue]:
    source_counts = count_linebreaks(str(record["source_zh"]))
    target_counts = count_linebreaks(str(record["target_ja"]))
    if source_counts == target_counts:
        return []

    return [
        Issue(
            string_id=str(record["string_id"]),
            checker="linebreak",
            issue_type="linebreak_mismatch",
            severity="major",
            message="必要换行在源文和日语译文中的数量不一致。",
            evidence={"source": source_counts, "target": target_counts},
        )
    ]
