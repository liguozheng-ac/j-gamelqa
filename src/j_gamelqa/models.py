"""Shared output models for rule checkers and future LLM evaluators."""

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class Issue:
    """One localization QA finding tied to a single string."""

    string_id: str
    checker: str
    issue_type: str
    severity: str
    message: str
    source_span: str | None = None
    target_span: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)
    needs_human_review: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly representation."""
        return asdict(self)
