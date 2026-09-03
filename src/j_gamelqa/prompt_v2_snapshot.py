"""Deterministic documentation snapshot for the real Prompt v2 builder."""

import argparse
import hashlib
from pathlib import Path

from j_gamelqa.io import load_glossary
from j_gamelqa.prompt_snapshot import DEMO_RECORD
from j_gamelqa.prompts import CONTEXT_INPUT_FIELDS, LLMInputMode
from j_gamelqa.prompts_v2 import PROMPT_VERSION, build_evaluator_prompt_v2


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest().upper()


def build_v2_snapshot_prompts(
    glossary: list[dict[str, str]],
) -> dict[str, str]:
    return {
        "without_context": build_evaluator_prompt_v2(
            DEMO_RECORD, glossary, LLMInputMode.WITHOUT_CONTEXT
        ),
        "with_context": build_evaluator_prompt_v2(
            DEMO_RECORD, glossary, LLMInputMode.WITH_CONTEXT
        ),
    }


def render_prompt_v2_snapshot(glossary: list[dict[str, str]]) -> str:
    prompts = build_v2_snapshot_prompts(glossary)
    context_fields = ", ".join(f"`{field}`" for field in CONTEXT_INPUT_FIELDS)
    return (
        "# Prompt v2 Snapshot\n\n"
        f"- Prompt version: `{PROMPT_VERSION}`\n"
        "- Generator: `j_gamelqa.prompts_v2.build_evaluator_prompt_v2`\n"
        "- Base: frozen Prompt v1 plus taxonomy-boundary guidance\n"
        "- Sample source: dedicated synthetic documentation demo; not DEV or Test data\n"
        f"- Without Context SHA-256: `{_sha256_text(prompts['without_context'])}`\n"
        f"- With Context SHA-256: `{_sha256_text(prompts['with_context'])}`\n\n"
        "This snapshot contains the exact Prompt v2 strings produced by the real "
        "builder. Prompt v2 remains zero-shot and retains the Prompt v1 JSON contract.\n\n"
        "## Without Context Example\n\n"
        "~~~text\n"
        f"{prompts['without_context']}\n"
        "~~~\n\n"
        "## With Context Example\n\n"
        f"This mode adds exactly: {context_fields}.\n\n"
        "~~~text\n"
        f"{prompts['with_context']}\n"
        "~~~\n"
    )


def write_prompt_v2_snapshot(
    output_path: str | Path,
    glossary_path: str | Path,
) -> Path:
    destination = Path(output_path)
    if destination.exists():
        raise FileExistsError(f"Prompt v2 snapshot already exists: {destination}")
    glossary = load_glossary(glossary_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(render_prompt_v2_snapshot(glossary), encoding="utf-8")
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate the deterministic Prompt v2 documentation snapshot."
    )
    parser.add_argument(
        "--glossary",
        type=Path,
        default=PROJECT_ROOT / "data" / "glossary.csv",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "docs" / "prompt_v2_snapshot.md",
    )
    args = parser.parse_args()
    print(write_prompt_v2_snapshot(args.output, args.glossary))


if __name__ == "__main__":
    main()
