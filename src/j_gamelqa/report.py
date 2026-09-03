"""JSON, CSV, and Excel exports for unified QA issues."""

import json
from pathlib import Path

import pandas as pd

from j_gamelqa.models import Issue


REPORT_FIELDS = (
    "string_id",
    "checker",
    "issue_type",
    "severity",
    "message",
    "source_span",
    "target_span",
    "evidence",
    "needs_human_review",
)


def _tabular_records(issues: list[Issue]) -> list[dict[str, object]]:
    records = []
    for issue in issues:
        record = issue.to_dict()
        record["evidence"] = json.dumps(record["evidence"], ensure_ascii=False)
        records.append(record)
    return records


def write_reports(
    issues: list[Issue], output_dir: str | Path
) -> dict[str, Path]:
    """Write the same issue collection to JSON, CSV, and XLSX."""
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)

    paths = {
        "json": destination / "rule_baseline.json",
        "csv": destination / "rule_baseline.csv",
        "xlsx": destination / "rule_baseline.xlsx",
    }

    json_payload = [issue.to_dict() for issue in issues]
    paths["json"].write_text(
        json.dumps(json_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    frame = pd.DataFrame(_tabular_records(issues), columns=REPORT_FIELDS)
    frame.to_csv(paths["csv"], index=False, encoding="utf-8-sig")
    frame.to_excel(paths["xlsx"], index=False, sheet_name="Rule Issues")
    return paths
