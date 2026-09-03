"""Run the deterministic rule pipeline on the public synthetic demo."""

import json
from pathlib import Path

from j_gamelqa.io import load_dev_dataset, load_glossary
from j_gamelqa.rule_engine import evaluate_dataframe


EXAMPLES_DIR = Path(__file__).resolve().parent


def main() -> None:
    frame = load_dev_dataset(EXAMPLES_DIR / "example_input.csv")
    glossary = load_glossary(EXAMPLES_DIR / "example_glossary.csv")
    issues = evaluate_dataframe(frame, glossary)
    print(
        json.dumps(
            [issue.to_dict() for issue in issues],
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
