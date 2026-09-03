"""Provider-neutral Japanese LLM evaluation and response parsing contract."""

import json
from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Callable

from j_gamelqa.io import VALID_SEVERITIES
from j_gamelqa.models import Issue
from j_gamelqa.prompts import LLMInputMode, build_evaluator_prompt
from j_gamelqa.taxonomy import REGISTERED_ISSUE_TYPES


LLMProvider = Callable[[str], str]

TOP_LEVEL_FIELDS = frozenset({"string_id", "issues"})
ISSUE_FIELDS = frozenset(
    {
        "issue_type",
        "severity",
        "source_span",
        "target_span",
        "evidence",
    }
)


@dataclass(slots=True)
class LLMProtocolDiagnostics:
    """Machine-readable protocol diagnostics retained beside raw responses."""

    parse_failures: list[str] = field(default_factory=list)
    schema_failures: list[str] = field(default_factory=list)
    validation_failures: list[str] = field(default_factory=list)
    unknown_issue_types: list[str] = field(default_factory=list)
    duplicate_predictions: list[dict[str, object]] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class LLMParseResult:
    """A raw response, validated predictions, and transparent diagnostics."""

    expected_string_id: str
    raw_response: str
    response_string_id: str | None
    predictions: list[Issue]
    diagnostics: LLMProtocolDiagnostics

    @property
    def is_valid(self) -> bool:
        return not (
            self.diagnostics.parse_failures
            or self.diagnostics.schema_failures
            or self.diagnostics.validation_failures
        )


@dataclass(slots=True)
class LLMEvaluationRun:
    """One provider-neutral evaluator call and its complete protocol result."""

    input_mode: LLMInputMode
    prompt: str
    result: LLMParseResult


def _schema_failure(
    expected_string_id: str,
    raw_response: str,
    response_string_id: str | None,
    messages: list[str],
) -> LLMParseResult:
    diagnostics = LLMProtocolDiagnostics(schema_failures=messages)
    return LLMParseResult(
        expected_string_id=expected_string_id,
        raw_response=raw_response,
        response_string_id=response_string_id,
        predictions=[],
        diagnostics=diagnostics,
    )


def _validate_issue_payload(issue_payload: object, index: int) -> list[str]:
    location = f"issues[{index}]"
    if not isinstance(issue_payload, dict):
        return [f"{location} must be an object"]

    fields = set(issue_payload)
    missing = sorted(ISSUE_FIELDS - fields)
    extra = sorted(fields - ISSUE_FIELDS)
    failures = []
    if missing:
        failures.append(f"{location} is missing fields: {', '.join(missing)}")
    if extra:
        failures.append(f"{location} has unexpected fields: {', '.join(extra)}")
    if missing or extra:
        return failures

    issue_type = issue_payload["issue_type"]
    severity = issue_payload["severity"]
    source_span = issue_payload["source_span"]
    target_span = issue_payload["target_span"]
    evidence = issue_payload["evidence"]

    if not isinstance(issue_type, str) or not issue_type.strip():
        failures.append(f"{location}.issue_type must be a non-empty string")
    if not isinstance(severity, str):
        failures.append(f"{location}.severity must be a string")
    elif severity not in VALID_SEVERITIES:
        failures.append(
            f"{location}.severity must be one of: "
            + ", ".join(sorted(VALID_SEVERITIES))
        )
    if not isinstance(source_span, str):
        failures.append(f"{location}.source_span must be a string")
    if not isinstance(target_span, str):
        failures.append(f"{location}.target_span must be a string")
    if not isinstance(evidence, str) or not evidence.strip():
        failures.append(f"{location}.evidence must be a non-empty string")
    return failures


def parse_llm_response(
    raw_response: str, expected_string_id: str
) -> LLMParseResult:
    """Parse strict JSON and convert valid predictions to the shared Issue model."""
    diagnostics = LLMProtocolDiagnostics()
    try:
        payload = json.loads(raw_response.strip())
    except (json.JSONDecodeError, TypeError) as exc:
        diagnostics.parse_failures.append(str(exc))
        return LLMParseResult(
            expected_string_id=expected_string_id,
            raw_response=raw_response,
            response_string_id=None,
            predictions=[],
            diagnostics=diagnostics,
        )

    if not isinstance(payload, dict):
        return _schema_failure(
            expected_string_id,
            raw_response,
            None,
            ["top-level response must be an object"],
        )

    response_string_id = (
        payload.get("string_id") if isinstance(payload.get("string_id"), str) else None
    )
    fields = set(payload)
    missing = sorted(TOP_LEVEL_FIELDS - fields)
    extra = sorted(fields - TOP_LEVEL_FIELDS)
    schema_failures = []
    if missing:
        schema_failures.append(
            "top-level response is missing fields: " + ", ".join(missing)
        )
    if extra:
        schema_failures.append(
            "top-level response has unexpected fields: " + ", ".join(extra)
        )
    if "string_id" in payload and not isinstance(payload["string_id"], str):
        schema_failures.append("string_id must be a string")
    if "issues" in payload and not isinstance(payload["issues"], list):
        schema_failures.append("issues must be a list")
    if schema_failures:
        return _schema_failure(
            expected_string_id,
            raw_response,
            response_string_id,
            schema_failures,
        )

    for index, issue_payload in enumerate(payload["issues"]):
        schema_failures.extend(_validate_issue_payload(issue_payload, index))
    if schema_failures:
        return _schema_failure(
            expected_string_id,
            raw_response,
            response_string_id,
            schema_failures,
        )

    if response_string_id != expected_string_id:
        diagnostics.validation_failures.append(
            f"response string_id {response_string_id!r} does not match "
            f"expected {expected_string_id!r}"
        )
        return LLMParseResult(
            expected_string_id=expected_string_id,
            raw_response=raw_response,
            response_string_id=response_string_id,
            predictions=[],
            diagnostics=diagnostics,
        )

    predictions = []
    for issue_payload in payload["issues"]:
        issue_type = issue_payload["issue_type"].strip()
        predictions.append(
            Issue(
                string_id=response_string_id,
                checker="japanese_llm",
                issue_type=issue_type,
                severity=issue_payload["severity"],
                message=f"Japanese LLM evaluator detected {issue_type}.",
                source_span=issue_payload["source_span"] or None,
                target_span=issue_payload["target_span"] or None,
                evidence={"reason": issue_payload["evidence"].strip()},
                needs_human_review=True,
            )
        )

    diagnostics.unknown_issue_types = sorted(
        {
            prediction.issue_type
            for prediction in predictions
            if prediction.issue_type not in REGISTERED_ISSUE_TYPES
        }
    )
    key_counts = Counter(
        (prediction.string_id, prediction.issue_type)
        for prediction in predictions
    )
    diagnostics.duplicate_predictions = [
        {"string_id": key[0], "issue_type": key[1], "count": count}
        for key, count in sorted(key_counts.items())
        if count > 1
    ]
    return LLMParseResult(
        expected_string_id=expected_string_id,
        raw_response=raw_response,
        response_string_id=response_string_id,
        predictions=predictions,
        diagnostics=diagnostics,
    )


def run_llm_evaluator(
    record: dict[str, object],
    glossary: list[dict[str, str]],
    mode: LLMInputMode,
    provider: LLMProvider,
) -> LLMEvaluationRun:
    """Build a prompt, call an injected provider, and parse its raw response."""
    prompt = build_evaluator_prompt(record, glossary, mode)
    raw_response = provider(prompt)
    result = parse_llm_response(raw_response, str(record["string_id"]))
    return LLMEvaluationRun(input_mode=mode, prompt=prompt, result=result)
