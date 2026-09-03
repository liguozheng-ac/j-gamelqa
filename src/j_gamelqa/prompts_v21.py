"""Prompt v2.1: a minimal, subtractive patch built directly on frozen v1."""

from j_gamelqa.prompts import LLMInputMode, build_evaluator_prompt


PROMPT_VERSION = "v2.1"

MINIMAL_BOUNDARY_GUIDANCE = """Minimal evaluation guidance
- Use mistranslation only when the source meaning is materially changed, contradicted, or distorted. If the meaning is substantially preserved but the Japanese is unnatural because of source-language interference, use translationese. Do not use mistranslation merely because the Japanese sounds awkward or stylistically inappropriate.
- Do not assign multiple issue types to the same underlying problem unless each issue has independent evidence.
- Relationship or hierarchy alone is not sufficient evidence for keigo_mismatch or character_voice_mismatch. The target expression and relevant context must support the issue together.
- Do not report an issue unless the relevant meaning difference is actually supported by the source and target.
- Write evidence as one short plain English sentence. Avoid quotation marks, line breaks, and internal deliberation.
- Return JSON only."""


def build_evaluator_prompt_v21(
    record: dict[str, object],
    glossary: list[dict[str, str]],
    mode: LLMInputMode,
) -> str:
    """Add the v2.1 minimal guidance without modifying Prompt v1 or v2."""
    prompt_v1 = build_evaluator_prompt(record, glossary, mode)
    input_marker = "\n\nInput\n"
    if prompt_v1.count(input_marker) != 1:
        raise RuntimeError("frozen Prompt v1 no longer has one Input section")
    return prompt_v1.replace(
        input_marker,
        "\n\n" + MINIMAL_BOUNDARY_GUIDANCE + input_marker,
        1,
    )
