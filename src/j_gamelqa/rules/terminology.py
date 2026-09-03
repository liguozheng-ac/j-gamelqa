"""Exact-match terminology checks backed by the project glossary."""

from j_gamelqa.models import Issue


def _forbidden_terms(raw_value: object) -> list[str]:
    return [term.strip() for term in str(raw_value).split("|") if term.strip()]


def check_terminology_issues(
    record: dict[str, object], glossary: list[dict[str, str]]
) -> list[Issue]:
    source_text = str(record["source_zh"])
    target_text = str(record["target_ja"])
    issues = []

    for entry in glossary:
        source_term = entry["source_term"].strip()
        approved_ja = entry["approved_ja"].strip()
        forbidden = _forbidden_terms(entry.get("forbidden_ja", ""))
        if not source_term or source_term not in source_text:
            continue

        used_forbidden = [term for term in forbidden if term in target_text]
        evidence = {
            "source_term": source_term,
            "approved_ja": approved_ja,
            "forbidden_ja": forbidden,
            "used_forbidden": used_forbidden,
        }

        if used_forbidden:
            issues.append(
                Issue(
                    string_id=str(record["string_id"]),
                    checker="terminology",
                    issue_type="terminology_forbidden",
                    severity="major",
                    message=f"术语“{source_term}”使用了禁用译法。",
                    source_span=source_term,
                    target_span=", ".join(used_forbidden),
                    evidence=evidence,
                    needs_human_review=True,
                )
            )
        elif approved_ja and approved_ja not in target_text:
            issues.append(
                Issue(
                    string_id=str(record["string_id"]),
                    checker="terminology",
                    issue_type="terminology_not_approved",
                    severity="major",
                    message=f"术语“{source_term}”未使用批准译法“{approved_ja}”。",
                    source_span=source_term,
                    evidence=evidence,
                    needs_human_review=True,
                )
            )

    return issues
