"""Rule-only baseline orchestration."""

import argparse
import json
from pathlib import Path

import pandas as pd

from j_gamelqa.io import load_dataset, load_glossary
from j_gamelqa.models import Issue
from j_gamelqa.rules.length import check_length_issues
from j_gamelqa.rules.linebreak import check_linebreak_issues
from j_gamelqa.rules.markup import check_markup_issues
from j_gamelqa.rules.number import check_number_issues
from j_gamelqa.rules.placeholder import check_placeholder_issues
from j_gamelqa.rules.terminology import check_terminology_issues


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PREDICTION_FIELDS = (
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


def evaluate_record(
    record: dict[str, object], glossary: list[dict[str, str]]
) -> list[Issue]:
    """Run every deterministic checker and collect all findings."""
    issues = []
    issues.extend(check_placeholder_issues(record))
    issues.extend(check_number_issues(record))
    issues.extend(check_markup_issues(record))
    issues.extend(check_linebreak_issues(record))
    issues.extend(check_length_issues(record))
    issues.extend(check_terminology_issues(record, glossary))
    return issues


def evaluate_dataframe(
    frame: pd.DataFrame, glossary: list[dict[str, str]]
) -> list[Issue]:
    """Evaluate all rows without exposing expected labels to the checkers."""
    missing = [field for field in PREDICTION_FIELDS if field not in frame.columns]
    if missing:
        raise ValueError(f"prediction input is missing fields: {', '.join(missing)}")

    issues = []
    prediction_frame = frame.loc[:, PREDICTION_FIELDS]
    for record in prediction_frame.to_dict(orient="records"):
        issues.extend(evaluate_record(record, glossary))
    return issues


def run_baseline(
    dataset_path: str | Path, glossary_path: str | Path
) -> tuple[pd.DataFrame, list[Issue]]:
    frame = load_dataset(dataset_path)
    glossary = load_glossary(glossary_path)
    return frame, evaluate_dataframe(frame, glossary)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the J-GameLQA rule baseline.")
    parser.add_argument("--input", type=Path, default=PROJECT_ROOT / "data" / "pilot.csv")
    parser.add_argument(
        "--glossary", type=Path, default=PROJECT_ROOT / "data" / "glossary.csv"
    )
    parser.add_argument(
        "--output-dir", type=Path, default=PROJECT_ROOT / "outputs"
    )
    args = parser.parse_args()

    _, issues = run_baseline(args.input, args.glossary)
    from j_gamelqa.report import write_reports

    paths = write_reports(issues, args.output_dir)
    summary = {
        "issue_count": len(issues),
        "issues": [issue.to_dict() for issue in issues],
        "reports": {name: str(path) for name, path in paths.items()},
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
