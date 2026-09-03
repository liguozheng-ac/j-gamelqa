"""Prompt v2: minimal taxonomy-boundary guidance layered onto frozen Prompt v1."""

from j_gamelqa.prompts import LLMInputMode, build_evaluator_prompt


PROMPT_VERSION = "v2"

TAXONOMY_BOUNDARY_GUIDANCE = """Taxonomy boundary guidance
- Use mistranslation only when the target changes, contradicts, or materially distorts the propositional meaning of the source. It is not a generic fallback label.
- If meaning is substantially preserved but the Japanese is unnatural because of source-language interference, use translationese rather than mistranslation.
- Prefer a specific supported type such as keigo_mismatch, first_person_mismatch, or character_voice_mismatch when it fully explains the problem. Add a generic semantic type only for a separate meaning error with distinct evidence.
- Relationship and context are evidence, not automatic proof of a violation. Consider the scene, established relationship, character style, and surrounding context together.
- Use omission only when meaningful source content is genuinely absent: it is neither expressed, implied, nor preserved through natural Japanese restructuring or reasonable condensation.
- Use addition only when the target introduces new meaning unsupported by both the source and reasonable context. Natural explicitation, grammatical completion, and UI localization adaptation are not automatically additions.
- Do not repackage a purely technical placeholder, number, markup, line-break, length, or terminology problem as addition, omission, or mistranslation unless an independent semantic problem also exists.
- Before emitting an issue, ensure its evidence is directly supported by the supplied source, target, or context."""

FINAL_CONSISTENCY_RULES = """Final consistency rules
Apply these checks silently before returning the JSON:
- Do not force an issue.
- Prefer the most specific supported issue type.
- Do not duplicate one underlying problem across generic and specific labels without independent evidence.
- Do not treat context alone as proof of an error.
- Ensure every issue has direct textual or contextual support.
- Return only the required JSON; do not output these checks or hidden reasoning."""


def build_evaluator_prompt_v2(
    record: dict[str, object],
    glossary: list[dict[str, str]],
    mode: LLMInputMode,
) -> str:
    """Add concise boundary guidance without changing frozen Prompt v1."""
    prompt_v1 = build_evaluator_prompt(record, glossary, mode)
    input_marker = "\n\nInput\n"
    if prompt_v1.count(input_marker) != 1:
        raise RuntimeError("frozen Prompt v1 no longer has one Input section")
    guidance = (
        "\n\n"
        + TAXONOMY_BOUNDARY_GUIDANCE
        + "\n\n"
        + FINAL_CONSISTENCY_RULES
    )
    return prompt_v1.replace(input_marker, guidance + input_marker, 1)
