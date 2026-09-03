"""Checks target text against the configured maximum length."""

from j_gamelqa.models import Issue


def check_length_issues(record: dict[str, object]) -> list[Issue]:
    raw_limit = record.get("max_length")
    if raw_limit is None or str(raw_limit).strip() == "":
        return []

    try:
        max_length = int(str(raw_limit))
    except ValueError as exc:
        raise ValueError(f"max_length must be an integer: {raw_limit!r}") from exc

    target_text = str(record["target_ja"])
    target_length = len(target_text)
    if target_length <= max_length:
        return []

    return [
        Issue(
            string_id=str(record["string_id"]),
            checker="length",
            issue_type="length_overflow",
            severity="minor",
            message=f"日语译文长度 {target_length} 超过限制 {max_length}。",
            target_span=target_text,
            evidence={
                "target_length": target_length,
                "max_length": max_length,
                "overflow": target_length - max_length,
            },
        )
    ]
