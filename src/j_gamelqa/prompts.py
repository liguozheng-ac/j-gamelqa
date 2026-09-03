"""Prompt and input construction for the provider-neutral Japanese evaluator."""

import json
from enum import Enum

from j_gamelqa.io import VALID_SEVERITIES
from j_gamelqa.taxonomy import ISSUE_TYPE_DEFINITIONS


class LLMInputMode(str, Enum):
    """Controls whether game and character context is included."""

    WITHOUT_CONTEXT = "without_context"
    WITH_CONTEXT = "with_context"


BASE_INPUT_FIELDS = (
    "string_id",
    "source_zh",
    "target_ja",
    "string_type",
    "max_length",
)

CONTEXT_INPUT_FIELDS = (
    "speaker",
    "addressee",
    "scene",
    "relationship",
    "context_before",
    "context_after",
)


def applicable_glossary_constraints(
    source_text: str, glossary: list[dict[str, str]]
) -> list[dict[str, object]]:
    """Return exact glossary entries whose source term occurs in the input."""
    constraints = []
    for entry in glossary:
        source_term = entry["source_term"].strip()
        if not source_term or source_term not in source_text:
            continue
        forbidden_terms = [
            term.strip()
            for term in entry.get("forbidden_ja", "").split("|")
            if term.strip()
        ]
        constraints.append(
            {
                "source_term": source_term,
                "approved_ja": entry["approved_ja"].strip(),
                "forbidden_ja": forbidden_terms,
            }
        )
    return constraints


def build_llm_input(
    record: dict[str, object],
    glossary: list[dict[str, str]],
    mode: LLMInputMode,
) -> dict[str, object]:
    """Build the controlled evaluator input for one localization record."""
    if not isinstance(mode, LLMInputMode):
        raise ValueError(f"unsupported LLM input mode: {mode!r}")

    missing_fields = [
        field
        for field in BASE_INPUT_FIELDS
        if field not in record
    ]
    if mode is LLMInputMode.WITH_CONTEXT:
        missing_fields.extend(
            field for field in CONTEXT_INPUT_FIELDS if field not in record
        )
    if missing_fields:
        raise ValueError(
            "LLM input record is missing fields: " + ", ".join(missing_fields)
        )

    payload = {field: record[field] for field in BASE_INPUT_FIELDS}
    payload["applicable_glossary_constraints"] = applicable_glossary_constraints(
        str(record["source_zh"]), glossary
    )
    if mode is LLMInputMode.WITH_CONTEXT:
        payload.update({field: record[field] for field in CONTEXT_INPUT_FIELDS})
    return payload


def _taxonomy_text() -> str:
    return "\n".join(
        f"- {issue_type}: {ISSUE_TYPE_DEFINITIONS[issue_type]}"
        for issue_type in sorted(ISSUE_TYPE_DEFINITIONS)
    )


def build_evaluator_prompt(
    record: dict[str, object],
    glossary: list[dict[str, str]],
    mode: LLMInputMode,
) -> str:
    """Build the shared zero-shot prompt, changing only the input payload by mode."""
    evaluator_input = build_llm_input(record, glossary, mode)
    allowed_severities = ", ".join(sorted(VALID_SEVERITIES))
    output_contract = {
        "string_id": "<copy the input string_id exactly>",
        "issues": [
            {
                "issue_type": "<one registered issue type>",
                "severity": f"<one of: {allowed_severities}>",
                "source_span": "<relevant source text or empty string>",
                "target_span": "<relevant target text or empty string>",
                "evidence": "<concise English reason for a QA reviewer>",
            }
        ],
    }

    return "\n\n".join(
        [
            (
                "Role and task\n"
                "You are a Japanese game-localization QA evaluator. Evaluate the "
                "Japanese target against the Chinese source and all supplied evidence."
            ),
            "Registered issue types\n" + _taxonomy_text(),
            (
                "Evaluation rules\n"
                "- Report only genuine issues supported by the supplied input.\n"
                "- An acceptable translation must return an empty issues list.\n"
                "- One string may contain multiple different issue types.\n"
                "- Use only the registered issue types.\n"
                "- Preserve severity and spans for review; do not output confidence scores.\n"
                "- Evidence must be concise English QA justification, not hidden reasoning.\n"
                "- Return JSON only, with no Markdown or surrounding prose."
            ),
            (
                "Input\n"
                + json.dumps(evaluator_input, ensure_ascii=False, indent=2)
            ),
            (
                "Required JSON contract\n"
                + json.dumps(output_contract, ensure_ascii=False, indent=2)
            ),
        ]
    )
